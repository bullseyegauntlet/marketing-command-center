#!/usr/bin/env python3
"""
Engagement Re-check Pipeline
Runs every 4 hours via cron. Queries posts ingested in the last 72 hours
that are not yet flagged as popular, then re-fetches current metrics and
flags any that now cross the thresholds.

X: batch-fetches metrics via GET /2/tweets?ids=... (100 per request)
Slack: re-checks reply count via conversations.replies
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL                          = os.getenv('DATABASE_URL')
X_API_KEY                       = os.getenv('X_API_KEY')
X_API_SECRET                    = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN                  = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET           = os.getenv('X_ACCESS_TOKEN_SECRET')
SLACK_TOKEN                     = os.getenv('SLACK_BOT_TOKEN')
ALERT_CHANNEL                   = os.getenv('SLACK_ALERT_CHANNEL')

POPULAR_THRESHOLD_X_VIEWS       = int(os.getenv('POPULAR_THRESHOLD_X_VIEWS', 50000))
POPULAR_THRESHOLD_X_LIKES       = int(os.getenv('POPULAR_THRESHOLD_X_LIKES', 500))
POPULAR_THRESHOLD_X_REPOSTS     = int(os.getenv('POPULAR_THRESHOLD_X_REPOSTS', 100))
POPULAR_THRESHOLD_X_REPLIES     = int(os.getenv('POPULAR_THRESHOLD_X_REPLIES', 100))
POPULAR_THRESHOLD_SLACK_REPLIES   = int(os.getenv('POPULAR_THRESHOLD_SLACK_REPLIES', 20))
POPULAR_THRESHOLD_REDDIT_UPVOTES  = int(os.getenv('POPULAR_THRESHOLD_REDDIT_UPVOTES', 100))
POPULAR_THRESHOLD_REDDIT_COMMENTS = int(os.getenv('POPULAR_THRESHOLD_REDDIT_COMMENTS', 50))
POPULAR_EXCLUDED_AUTHORS        = {a.strip().lower().lstrip('@')
                                   for a in os.getenv('POPULAR_EXCLUDED_AUTHORS', 'jason,eriktorenberg,austen').split(',') if a.strip()}

RECHECK_WINDOW_HOURS = int(os.getenv('RECHECK_WINDOW_HOURS', 72))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


def get_auth() -> OAuth1:
    return OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)


def x_get(url: str, params: dict, retries=3) -> dict:
    auth = get_auth()
    for attempt in range(retries):
        try:
            r = requests.get(url, auth=auth, params=params, timeout=15)
            if r.status_code == 429:
                wait = int(r.headers.get('x-rate-limit-reset', time.time() + 60)) - int(time.time())
                wait = max(wait, 5)
                log.warning(f'Rate limited, waiting {wait}s')
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json()
            log.error(f'X API error {r.status_code}: {r.text[:200]}')
            return {'error': r.text}
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f'Request failed (attempt {attempt+1}): {e}. Retrying in {wait}s')
            time.sleep(wait)
    return {'error': 'max_retries_exceeded'}


def slack_get(endpoint: str, params: dict, retries=3) -> dict:
    headers = {'Authorization': f'Bearer {SLACK_TOKEN}'}
    for attempt in range(retries):
        try:
            r = requests.get(f'https://slack.com/api/{endpoint}', headers=headers,
                             params=params, timeout=15)
            data = r.json()
            if data.get('ok'):
                return data
            if data.get('error') == 'ratelimited':
                wait = int(r.headers.get('Retry-After', 5))
                log.warning(f'Slack rate limited, waiting {wait}s')
                time.sleep(wait)
                continue
            return data
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f'Slack request failed (attempt {attempt+1}): {e}. Retrying in {wait}s')
            time.sleep(wait)
    return {'ok': False, 'error': 'max_retries_exceeded'}


def send_aggregated_alert(newly_flagged: list):
    """Send a single concise message listing all newly flagged posts this cycle."""
    if not newly_flagged or not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    lines = [f'🔥 *{len(newly_flagged)} new popular post{"s" if len(newly_flagged) > 1 else ""}*']
    for post in newly_flagged:
        author = post.get('author', 'unknown')
        url    = post.get('source_url', '')
        lines.append(f'• @{author}: {url}')
    message = '\n'.join(lines)
    try:
        requests.post('https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)
    except Exception as e:
        log.error(f'Failed to send aggregated alert: {e}')


def flag_popular(cur, conn, post_id: str, triggered_by: str, metric_value: int) -> bool:
    """Insert into popular_posts. Returns True if newly inserted (not a dupe)."""
    cur.execute('''
        INSERT INTO popular_posts (post_id, triggered_by, metric_value)
        VALUES (%s, %s, %s)
        ON CONFLICT (post_id) DO NOTHING
    ''', (post_id, triggered_by, metric_value))
    conn.commit()
    return cur.rowcount > 0


def recheck_x_posts(cur, conn, posts: list) -> list:
    """Batch-fetch current X metrics for a list of X posts and flag as needed."""
    flagged = []
    if not posts:
        return flagged

    # Map external_id -> post row
    id_map = {p['external_id']: p for p in posts}
    tweet_ids = list(id_map.keys())

    BATCH = 100
    for i in range(0, len(tweet_ids), BATCH):
        batch_ids = tweet_ids[i:i+BATCH]
        data = x_get('https://api.twitter.com/2/tweets', {
            'ids': ','.join(batch_ids),
            'tweet.fields': 'public_metrics,referenced_tweets',
        })
        if 'error' in data or not data.get('data'):
            log.warning(f'X metrics fetch failed or empty for batch {i//BATCH + 1}')
            continue

        for tweet in data['data']:
            tweet_id = tweet['id']
            post = id_map.get(tweet_id)
            if not post:
                continue

            # Skip retweets, quotes, and replies — only flag original posts
            referenced = tweet.get('referenced_tweets', [])
            ref_types = {r.get('type') for r in referenced} if referenced else set()
            if ref_types.intersection({'retweeted', 'quoted', 'replied_to'}):
                continue

            # Skip excluded authors
            if post.get('author', '').lower() in POPULAR_EXCLUDED_AUTHORS:
                continue

            metrics = tweet.get('public_metrics', {})
            views   = metrics.get('impression_count', 0)
            likes   = metrics.get('like_count', 0)
            reposts = metrics.get('retweet_count', 0)
            replies = metrics.get('reply_count', 0)

            triggered_by = None
            metric_value = 0

            if views >= POPULAR_THRESHOLD_X_VIEWS:
                triggered_by, metric_value = 'views', views
            elif likes >= POPULAR_THRESHOLD_X_LIKES:
                triggered_by, metric_value = 'likes', likes
            elif reposts >= POPULAR_THRESHOLD_X_REPOSTS:
                triggered_by, metric_value = 'reposts', reposts
            elif replies >= POPULAR_THRESHOLD_X_REPLIES:
                triggered_by, metric_value = 'replies', replies

            if not triggered_by:
                continue

            newly_flagged = flag_popular(cur, conn, str(post['id']), triggered_by, metric_value)
            if newly_flagged:
                log.info(f'Recheck flagged X post {post["id"]} ({triggered_by}: {metric_value})')
                flagged.append(post)

        log.info(f'Rechecked X batch {i//BATCH + 1} ({len(batch_ids)} tweets)')


    return flagged


def recheck_slack_posts(cur, conn, posts: list) -> list:
    """Re-fetch reply counts for Slack thread root messages and flag as needed."""
    flagged = []
    if not posts:
        return flagged

    for post in posts:
        # external_id for Slack is the message ts
        ts = post['external_id']
        channel = post.get('channel', '')
        if not channel:
            continue

        data = slack_get('conversations.replies', {
            'channel': channel,
            'ts': ts,
            'limit': 1,
            'inclusive': True,
        })
        if not data.get('ok'):
            log.warning(f'Failed to fetch replies for {ts}: {data.get("error")}')
            continue

        messages = data.get('messages', [])
        if not messages:
            continue

        parent = messages[0]
        reply_count = parent.get('reply_count', 0)

        if reply_count < POPULAR_THRESHOLD_SLACK_REPLIES:
            continue

        newly_flagged = flag_popular(cur, conn, str(post['id']), 'slack_thread_replies', reply_count)
        if newly_flagged:
            log.info(f'Recheck flagged Slack post {post["id"]} ({reply_count} replies)')
            flagged.append(post)
    return flagged


def recheck_reddit_posts(cur, conn, posts: list) -> list:
    """Re-fetch upvote/comment counts for Reddit posts via public API and flag as needed."""
    flagged = []
    if not posts:
        return flagged

    for post in posts:
        external_id = post.get('external_id', '')
        # external_id format: reddit_<post_id>
        post_id = external_id.replace('reddit_', '')
        if not post_id:
            continue

        try:
            r = requests.get(
                f'https://www.reddit.com/by_id/t3_{post_id}.json',
                params={'limit': 1},
                headers={'User-Agent': f'MCC-Monitor/1.0 by Bullseye_Gauntlet'},
                timeout=10,
            )
            if not r.ok:
                continue
            children = r.json().get('data', {}).get('children', [])
            if not children:
                continue
            data = children[0].get('data', {})
        except Exception as e:
            log.warning(f'Failed to fetch Reddit post {post_id}: {e}')
            continue

        upvotes  = data.get('score', 0)
        comments = data.get('num_comments', 0)

        triggered_by = None
        metric_value = 0
        if upvotes >= POPULAR_THRESHOLD_REDDIT_UPVOTES:
            triggered_by, metric_value = 'upvotes', upvotes
        elif comments >= POPULAR_THRESHOLD_REDDIT_COMMENTS:
            triggered_by, metric_value = 'comments', comments

        if not triggered_by:
            continue

        newly_flagged = flag_popular(cur, conn, str(post['id']), triggered_by, metric_value)
        if newly_flagged:
            log.info(f'Recheck flagged Reddit post {post["id"]} ({triggered_by}: {metric_value})')
            flagged.append(post)
        time.sleep(0.5)  # be gentle with public API

    return flagged


def run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Fetch X posts from last RECHECK_WINDOW_HOURS not yet flagged as popular
        cur.execute('''
            SELECT p.id, p.external_id, p.author, p.content, p.source_url, p.channel
            FROM posts p
            LEFT JOIN popular_posts pp ON pp.post_id = p.id
            WHERE p.platform = 'x'
              AND p.ingested_at >= NOW() - INTERVAL '%s hours'
              AND pp.id IS NULL
        ''', (RECHECK_WINDOW_HOURS,))
        x_posts = [dict(r) for r in cur.fetchall()]
        log.info(f'Rechecking {len(x_posts)} X posts')
        flagged = recheck_x_posts(cur, conn, x_posts)

        # Fetch Slack posts from last RECHECK_WINDOW_HOURS not yet flagged
        # Only check thread roots (messages that have replies — we track external_id = ts)
        cur.execute('''
            SELECT p.id, p.external_id, p.author, p.content, p.source_url, p.channel
            FROM posts p
            LEFT JOIN popular_posts pp ON pp.post_id = p.id
            WHERE p.platform = 'slack'
              AND p.ingested_at >= NOW() - INTERVAL '%s hours'
              AND pp.id IS NULL
        ''', (RECHECK_WINDOW_HOURS,))
        slack_posts = [dict(r) for r in cur.fetchall()]
        log.info(f'Rechecking {len(slack_posts)} Slack posts')
        flagged += recheck_slack_posts(cur, conn, slack_posts)

        # Fetch Reddit posts from last RECHECK_WINDOW_HOURS not yet flagged
        cur.execute('''
            SELECT p.id, p.external_id, p.author, p.content, p.source_url, p.channel
            FROM posts p
            LEFT JOIN popular_posts pp ON pp.post_id = p.id
            WHERE p.platform = 'reddit'
              AND p.ingested_at >= NOW() - INTERVAL '%s hours'
              AND pp.id IS NULL
        ''', (RECHECK_WINDOW_HOURS,))
        reddit_posts = [dict(r) for r in cur.fetchall()]
        log.info(f'Rechecking {len(reddit_posts)} Reddit posts')
        flagged += recheck_reddit_posts(cur, conn, reddit_posts)

        send_aggregated_alert(flagged)
        log.info(f'Engagement recheck complete. {len(flagged)} newly flagged.')

    except Exception as e:
        log.error(f'Engagement recheck failed: {e}')
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
