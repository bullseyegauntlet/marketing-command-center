#!/usr/bin/env python3
"""
X (Twitter) Mentions Ingestion Pipeline
Searches X for posts explicitly mentioning Gauntlet AI using the recent search endpoint.
Runs every 4 hours via cron. Tags all results is_mention=TRUE.

Search query: "Gauntlet AI" OR gauntletai OR @GauntletAI -is:retweet lang:en

Uses the same auth, embedding, popular-threshold, and checkpoint patterns as x_ingestion.py.

Env vars: same as x_ingestion.py (no additional vars needed)
  DATABASE_URL, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET,
  OPENROUTER_API_KEY / OPENAI_API_KEY, SLACK_BOT_TOKEN, SLACK_ALERT_CHANNEL,
  POPULAR_THRESHOLD_X_VIEWS/LIKES/REPOSTS/REPLIES
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from openai import OpenAI
from requests_oauthlib import OAuth1

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL                = os.getenv('DATABASE_URL')
X_API_KEY             = os.getenv('X_API_KEY')
X_API_SECRET          = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN        = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
SLACK_TOKEN           = os.getenv('SLACK_BOT_TOKEN')
ALERT_CHANNEL         = os.getenv('SLACK_ALERT_CHANNEL')
OPENROUTER_API_KEY    = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY        = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY     = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL    = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL       = 'text-embedding-3-small'
DEAD_LETTER_PATH      = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_x_mentions.json')

# Search query — catches name, handle, and website; excludes pure retweets
X_MENTIONS_QUERY = os.getenv(
    'X_MENTIONS_QUERY',
    '"Gauntlet AI" OR gauntletai OR @GauntletAI OR gauntletai.com -is:retweet lang:en'
)

POPULAR_THRESHOLD_X_VIEWS   = int(os.getenv('POPULAR_THRESHOLD_X_VIEWS', 50000))
POPULAR_THRESHOLD_X_LIKES   = int(os.getenv('POPULAR_THRESHOLD_X_LIKES', 300))
POPULAR_THRESHOLD_X_REPOSTS = int(os.getenv('POPULAR_THRESHOLD_X_REPOSTS', 50))
POPULAR_THRESHOLD_X_REPLIES = int(os.getenv('POPULAR_THRESHOLD_X_REPLIES', 50))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


# ─── HTTP ──────────────────────────────────────────────────────────────────────

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


# ─── Helpers ───────────────────────────────────────────────────────────────────

def parse_datetime(dt_str: str) -> datetime:
    return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=None)


def get_embeddings(client: OpenAI, texts: list) -> list:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def send_alert(message: str):
    if not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    try:
        requests.post('https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)
    except Exception as e:
        log.error(f'Failed to send alert: {e}')


def log_dead_letter(post: dict, error: str):
    os.makedirs(os.path.dirname(DEAD_LETTER_PATH), exist_ok=True)
    entry = {'timestamp': datetime.utcnow().isoformat(), 'error': error, 'post': post}
    try:
        with open(DEAD_LETTER_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        log.error(f'Failed to write dead letter: {e}')


# ─── Popular Threshold Check ───────────────────────────────────────────────────

def send_popular_alert(post_data: dict, triggered_by: str, metric_value: int):
    if not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    metrics  = post_data.get('metrics', {})
    views    = metrics.get('impression_count', 0)
    likes    = metrics.get('like_count', 0)
    reposts  = metrics.get('retweet_count', 0)
    replies  = metrics.get('reply_count', 0)
    preview  = post_data.get('content', '')[:200]
    author   = post_data.get('author', 'unknown')
    url      = post_data.get('source_url', '')
    thresholds = {
        'views': POPULAR_THRESHOLD_X_VIEWS, 'likes': POPULAR_THRESHOLD_X_LIKES,
        'reposts': POPULAR_THRESHOLD_X_REPOSTS, 'replies': POPULAR_THRESHOLD_X_REPLIES,
    }
    message = (
        f'🔥 *Viral X Mention Detected*\n\n'
        f'*@{author}* is talking about Gauntlet AI:\n\n'
        f'> "{preview}"\n\n'
        f'👁 *{views:,} views*  ❤ *{likes:,} likes*  🔁 *{reposts:,} reposts*  💬 *{replies:,} replies*\n'
        f'📎 {url}\n\n'
        f'_Triggered by: {metric_value:,} {triggered_by} (threshold: {thresholds.get(triggered_by, "?"):,})_'
    )
    try:
        requests.post('https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)
    except Exception as e:
        log.error(f'Failed to send popular alert: {e}')


def check_popular_thresholds(cur, conn, post_id: str, post_data: dict):
    metrics  = post_data.get('metrics', {})
    views    = metrics.get('impression_count', 0)
    likes    = metrics.get('like_count', 0)
    reposts  = metrics.get('retweet_count', 0)
    replies  = metrics.get('reply_count', 0)

    triggered_by = None
    metric_value = 0
    if views   >= POPULAR_THRESHOLD_X_VIEWS:   triggered_by, metric_value = 'views',   views
    elif likes  >= POPULAR_THRESHOLD_X_LIKES:  triggered_by, metric_value = 'likes',   likes
    elif reposts>= POPULAR_THRESHOLD_X_REPOSTS:triggered_by, metric_value = 'reposts', reposts
    elif replies>= POPULAR_THRESHOLD_X_REPLIES:triggered_by, metric_value = 'replies', replies

    if not triggered_by:
        return
    try:
        cur.execute('''
            INSERT INTO popular_posts (post_id, triggered_by, metric_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (post_id) DO NOTHING
        ''', (post_id, triggered_by, metric_value))
        conn.commit()
        if cur.rowcount > 0:
            log.info(f'Flagged X mention {post_id} as popular ({triggered_by}: {metric_value})')
            send_popular_alert(post_data, triggered_by, metric_value)
    except Exception as e:
        log.error(f'Failed to flag popular post {post_id}: {e}')
        conn.rollback()


# ─── Search ────────────────────────────────────────────────────────────────────

def fetch_mentions(since_id: Optional[str] = None) -> tuple[list, dict]:
    """
    Search X for Gauntlet AI mentions using /2/tweets/search/recent.
    Returns (tweets, author_map).
    Paginates until results are exhausted or we hit since_id.
    """
    params = {
        'query': X_MENTIONS_QUERY,
        'max_results': 100,
        'tweet.fields': 'created_at,public_metrics,entities,author_id',
        'expansions': 'author_id',
        'user.fields': 'username',
        'sort_order': 'recency',
    }
    if since_id:
        params['since_id'] = since_id

    all_tweets = []
    author_map = {}
    max_pages  = 10  # cap at 1,000 tweets per run

    for page in range(max_pages):
        data = x_get('https://api.twitter.com/2/tweets/search/recent', params)
        if 'error' in data or 'errors' in data:
            log.error(f'X search error: {data}')
            break

        tweets = data.get('data', [])
        if not tweets:
            break

        all_tweets.extend(tweets)

        for user in data.get('includes', {}).get('users', []):
            author_map[user['id']] = user['username']

        meta       = data.get('meta', {})
        next_token = meta.get('next_token')
        if not next_token:
            break
        params['pagination_token'] = next_token
        time.sleep(1)  # be polite between pages

    return all_tweets, author_map


# ─── Main ──────────────────────────────────────────────────────────────────────

def run():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    cur.execute("SELECT last_id, consecutive_failures FROM ingestion_checkpoints WHERE source = 'x_mentions'")
    row      = cur.fetchone()
    since_id = row['last_id'] if row else None
    failures = row['consecutive_failures'] if row else 0

    try:
        log.info(f'Searching X for Gauntlet AI mentions (since_id: {since_id})')
        tweets, author_map = fetch_mentions(since_id)
        log.info(f'Fetched {len(tweets)} mention tweets')

        new_posts  = []
        latest_id  = since_id

        for tweet in tweets:
            tweet_id = tweet['id']

            if not latest_id or int(tweet_id) > int(latest_id):
                latest_id = tweet_id

            cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (tweet_id,))
            if cur.fetchone():
                continue

            author_id  = tweet.get('author_id', '')
            username   = author_map.get(author_id, author_id)
            content    = tweet.get('text', '')
            metrics    = tweet.get('public_metrics', {})
            created_at = parse_datetime(tweet.get('created_at', '1970-01-01T00:00:00.000Z'))
            source_url = f'https://x.com/{username}/status/{tweet_id}'

            links = []
            for url_obj in tweet.get('entities', {}).get('urls', []):
                expanded = url_obj.get('expanded_url', url_obj.get('url', ''))
                if expanded:
                    links.append(expanded)

            new_posts.append({
                'external_id': tweet_id,
                'author':      username,
                'content':     content,
                'source_url':  source_url,
                'published_at': created_at,
                'likes':    metrics.get('like_count', 0),
                'retweets': metrics.get('retweet_count', 0),
                'replies':  metrics.get('reply_count', 0),
                'views':    metrics.get('impression_count', 0),
                'links':    json.dumps(links),
                'metrics':  metrics,
            })

        if not new_posts:
            log.info('No new X mentions.')
        else:
            BATCH = 50
            for i in range(0, len(new_posts), BATCH):
                batch = new_posts[i:i + BATCH]
                texts = [p['content'] for p in batch]
                try:
                    embeddings = get_embeddings(openai_client, texts)
                except Exception as e:
                    log.error(f'Embedding failed: {e}')
                    embeddings = [None] * len(batch)

                for post, embedding in zip(batch, embeddings):
                    try:
                        cur.execute('''
                            INSERT INTO posts (
                                platform, external_id, author, content, source_url,
                                published_at, likes, retweets, replies, views,
                                channel, links, embedding, is_mention
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (external_id) DO NOTHING
                            RETURNING id
                        ''', (
                            'x', post['external_id'], post['author'], post['content'],
                            post['source_url'], post['published_at'],
                            post['likes'], post['retweets'], post['replies'], post['views'],
                            'x_mentions', post['links'], embedding,
                            True,  # is_mention = True for all search results
                        ))
                        row = cur.fetchone()
                        if row:
                            check_popular_thresholds(cur, conn, str(row['id']), post)
                    except Exception as e:
                        log.error(f'Insert failed for {post["external_id"]}: {e}')
                        log_dead_letter(post, str(e))
                        conn.rollback()

                conn.commit()
                log.info(f'Inserted batch {i // BATCH + 1} ({len(batch)} tweets)')

            log.info(f'X mentions ingestion complete: {len(new_posts)} new mentions')

        # Update checkpoint
        cur.execute('''
            INSERT INTO ingestion_checkpoints (source, last_id, last_run_at, status, consecutive_failures)
            VALUES ('x_mentions', %s, NOW(), 'success', 0)
            ON CONFLICT (source) DO UPDATE
            SET last_id = EXCLUDED.last_id, last_run_at = NOW(),
                status = 'success', consecutive_failures = 0
        ''', (latest_id,))
        conn.commit()

    except Exception as e:
        failures += 1
        cur.execute('''
            INSERT INTO ingestion_checkpoints (source, last_id, last_run_at, status, consecutive_failures)
            VALUES ('x_mentions', %s, NOW(), 'failed', %s)
            ON CONFLICT (source) DO UPDATE
            SET last_run_at = NOW(), status = 'failed', consecutive_failures = EXCLUDED.consecutive_failures
        ''', (since_id, failures))
        conn.commit()
        log.error(f'X mentions ingestion failed: {e}')
        if failures >= 2:
            send_alert(f'🚨 MCC: X mentions ingestion has failed {failures} times in a row.\nError: {e}')
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
