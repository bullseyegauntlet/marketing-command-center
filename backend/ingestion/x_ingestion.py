#!/usr/bin/env python3
"""
X (Twitter) Ingestion Pipeline
Fetches tweets from the gauntlet_graduates list and inserts into posts table.
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

DB_URL = os.getenv('DATABASE_URL')
X_API_KEY = os.getenv('X_API_KEY')
X_API_SECRET = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
X_LIST_ID = os.getenv('X_LIST_ID')
ALERT_CHANNEL = os.getenv('SLACK_ALERT_CHANNEL')
SLACK_TOKEN = os.getenv('SLACK_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL = 'text-embedding-3-small'
DEAD_LETTER_PATH = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_x.json')

# Popular post thresholds (configurable via env)
POPULAR_THRESHOLD_X_VIEWS    = int(os.getenv('POPULAR_THRESHOLD_X_VIEWS', 1000))
POPULAR_THRESHOLD_X_LIKES    = int(os.getenv('POPULAR_THRESHOLD_X_LIKES', 500))
POPULAR_THRESHOLD_X_REPOSTS  = int(os.getenv('POPULAR_THRESHOLD_X_REPOSTS', 100))
POPULAR_THRESHOLD_X_REPLIES  = int(os.getenv('POPULAR_THRESHOLD_X_REPLIES', 100))

# Authors to exclude from popular flagging (lowercase, no @)
POPULAR_EXCLUDED_AUTHORS = {a.strip().lower().lstrip('@')
                            for a in os.getenv('POPULAR_EXCLUDED_AUTHORS', 'jason').split(',') if a.strip()}

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
    requests.post('https://slack.com/api/chat.postMessage',
        headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
        json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)


def send_popular_alert(post_data: dict, triggered_by: str, metric_value: int):
    """Send a Slack alert for a newly flagged popular X post."""
    if not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    metrics = post_data.get('metrics', {})
    views = metrics.get('impression_count', 0)
    likes = metrics.get('like_count', 0)
    reposts = metrics.get('retweet_count', 0)
    replies = metrics.get('reply_count', 0)
    content_preview = post_data.get('content', '')[:200]
    author = post_data.get('author', 'unknown')
    url = post_data.get('source_url', '')

    metric_labels = {
        'views': f'{metric_value:,} views',
        'likes': f'{metric_value:,} likes',
        'reposts': f'{metric_value:,} reposts',
        'replies': f'{metric_value:,} replies',
    }
    trigger_label = metric_labels.get(triggered_by, f'{metric_value:,} {triggered_by}')

    thresholds = {
        'views': POPULAR_THRESHOLD_X_VIEWS,
        'likes': POPULAR_THRESHOLD_X_LIKES,
        'reposts': POPULAR_THRESHOLD_X_REPOSTS,
        'replies': POPULAR_THRESHOLD_X_REPLIES,
    }
    threshold_label = thresholds.get(triggered_by, '?')

    message = (
        f'🔥 *Viral X Post Detected*\n\n'
        f'*@{author}* posted something taking off:\n\n'
        f'> "{content_preview}"\n\n'
        f'👁 *{views:,} views*  ❤ *{likes:,} likes*  🔁 *{reposts:,} reposts*  💬 *{replies:,} replies*\n'
        f'📎 {url}\n\n'
        f'_Triggered by: {trigger_label} (threshold: {threshold_label:,})_'
    )
    try:
        requests.post('https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)
    except Exception as e:
        log.error(f'Failed to send popular alert: {e}')


def check_popular_thresholds(cur, conn, post_id: str, post_data: dict):
    """Check if a post crosses any popularity threshold. Insert into popular_posts if so."""
    metrics = post_data.get('metrics', {})
    views   = metrics.get('impression_count', 0)
    likes   = metrics.get('like_count', 0)
    reposts = metrics.get('retweet_count', 0)
    replies = metrics.get('reply_count', 0)

    triggered_by  = None
    metric_value  = 0

    if views >= POPULAR_THRESHOLD_X_VIEWS:
        triggered_by, metric_value = 'views', views
    elif likes >= POPULAR_THRESHOLD_X_LIKES:
        triggered_by, metric_value = 'likes', likes
    elif reposts >= POPULAR_THRESHOLD_X_REPOSTS:
        triggered_by, metric_value = 'reposts', reposts
    elif replies >= POPULAR_THRESHOLD_X_REPLIES:
        triggered_by, metric_value = 'replies', replies

    if not triggered_by:
        return

    try:
        cur.execute('''
            INSERT INTO popular_posts (post_id, triggered_by, metric_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (post_id) DO NOTHING
        ''', (post_id, triggered_by, metric_value))
        conn.commit()
        log.info(f'Flagged post {post_id} as popular ({triggered_by}: {metric_value})')
        send_popular_alert(post_data, triggered_by, metric_value)
    except Exception as e:
        log.error(f'Failed to flag popular post {post_id}: {e}')
        conn.rollback()


def log_dead_letter(tweet: dict, error: str):
    os.makedirs(os.path.dirname(DEAD_LETTER_PATH), exist_ok=True)
    entry = {'timestamp': datetime.utcnow().isoformat(), 'error': error, 'tweet': tweet}
    try:
        with open(DEAD_LETTER_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        log.error(f'Failed to write dead letter: {e}')


def fetch_list_tweets(since_id: Optional[str] = None) -> tuple[list, dict]:
    """Fetch tweets from X list since since_id. Returns (tweets, author_map).
    The /lists/:id/tweets endpoint doesn't support since_id — we paginate
    and stop when we see a tweet ID <= since_id."""
    base_url = f'https://api.twitter.com/2/lists/{X_LIST_ID}/tweets'
    params = {
        'max_results': 100,
        'tweet.fields': 'created_at,public_metrics,entities,author_id,referenced_tweets',
        'expansions': 'author_id',
        'user.fields': 'username',
        # public_metrics includes impression_count (views) since 2023 API update
    }

    all_tweets = []
    author_map = {}
    since_int = int(since_id) if since_id else 0
    max_pages = 50  # safety cap (~5000 tweets max per run)

    for page in range(max_pages):
        data = x_get(base_url, params)
        if 'error' in data or 'errors' in data:
            log.error(f'X API error: {data}')
            break

        tweets = data.get('data', [])
        if not tweets:
            break

        # Stop paginating once we see tweets we already have
        new_tweets = []
        done = False
        for t in tweets:
            if int(t['id']) <= since_int:
                done = True
                break
            new_tweets.append(t)

        all_tweets.extend(new_tweets)

        # Build author map from includes
        for user in data.get('includes', {}).get('users', []):
            author_map[user['id']] = user['username']

        if done:
            break

        meta = data.get('meta', {})
        next_token = meta.get('next_token')
        if not next_token:
            break
        params['pagination_token'] = next_token

    return all_tweets, author_map


def run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    cur.execute('SELECT last_id, consecutive_failures FROM ingestion_checkpoints WHERE source = %s', ('x',))
    row = cur.fetchone()
    since_id = row['last_id'] if row else None
    failures = row['consecutive_failures'] if row else 0

    try:
        log.info(f'Fetching X tweets from list {X_LIST_ID} (since_id: {since_id})')
        tweets, author_map = fetch_list_tweets(since_id)
        log.info(f'Fetched {len(tweets)} tweets')

        new_tweets = []
        latest_id = since_id

        for tweet in tweets:
            tweet_id = tweet['id']

            # Track latest for checkpoint
            if not latest_id or int(tweet_id) > int(latest_id):
                latest_id = tweet_id

            # Deduplicate
            cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (tweet_id,))
            if cur.fetchone():
                continue

            author_id = tweet.get('author_id', '')
            username = author_map.get(author_id, author_id)
            content = tweet.get('text', '')
            metrics = tweet.get('public_metrics', {})
            created_at = parse_datetime(tweet.get('created_at', '1970-01-01T00:00:00.000Z'))
            source_url = f'https://x.com/{username}/status/{tweet_id}'

            # Extract links from entities
            links = []
            for url_obj in tweet.get('entities', {}).get('urls', []):
                expanded = url_obj.get('expanded_url', url_obj.get('url', ''))
                if expanded:
                    links.append(expanded)

            # Skip retweets, quotes, and replies — only ingest original posts
            # by the list members themselves
            referenced = tweet.get('referenced_tweets', [])
            ref_types = {r.get('type') for r in referenced} if referenced else set()
            if ref_types.intersection({'retweeted', 'quoted', 'replied_to'}):
                continue

            new_tweets.append({
                'external_id': tweet_id,
                'author': username,
                'content': content,
                'source_url': source_url,
                'published_at': created_at,
                'likes': metrics.get('like_count', 0),
                'retweets': metrics.get('retweet_count', 0),
                'replies': metrics.get('reply_count', 0),
                'views': metrics.get('impression_count', 0),
                'links': json.dumps(links),
                '_metrics': metrics,
            })

        if not new_tweets:
            log.info('No new tweets.')
        else:
            # Generate embeddings in batches
            BATCH = 50
            for i in range(0, len(new_tweets), BATCH):
                batch = new_tweets[i:i+BATCH]
                texts = [p['content'] for p in batch]
                try:
                    embeddings = get_embeddings(openai_client, texts)
                except Exception as e:
                    log.error(f'Embedding failed: {e}')
                    embeddings = [None] * len(batch)

                for post, embedding in zip(batch, embeddings):
                    try:
                        cur.execute('''
                            INSERT INTO posts (platform, external_id, author, content, source_url,
                                published_at, likes, retweets, replies, views, channel, links, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (external_id) DO NOTHING
                            RETURNING id
                        ''', (
                            'x', post['external_id'], post['author'], post['content'],
                            post['source_url'], post['published_at'],
                            post['likes'], post['retweets'], post['replies'], post['views'],
                            'gauntlet_graduates', post['links'], embedding
                        ))
                        row = cur.fetchone()
                        if row and post['author'].lower() not in POPULAR_EXCLUDED_AUTHORS:
                            # Only check popularity for original posts (not retweets/quotes/replies)
                            # and excluded authors
                            check_popular_thresholds(cur, conn, str(row['id']), {
                                'author': post['author'],
                                'content': post['content'],
                                'source_url': post['source_url'],
                                'metrics': post['_metrics'],
                            })
                    except Exception as e:
                        log.error(f'Insert failed for {post["external_id"]}: {e}')
                        log_dead_letter(post, str(e))
                        conn.rollback()

                conn.commit()
                log.info(f'Inserted batch {i//BATCH + 1} ({len(batch)} tweets)')

            log.info(f'X ingestion complete: {len(new_tweets)} new tweets')

        # Update checkpoint
        cur.execute('''
            UPDATE ingestion_checkpoints
            SET last_id = %s, last_run_at = NOW(), status = %s, consecutive_failures = 0
            WHERE source = %s
        ''', (latest_id, 'success', 'x'))
        conn.commit()

    except Exception as e:
        failures += 1
        cur.execute('''
            UPDATE ingestion_checkpoints
            SET last_run_at = NOW(), status = %s, consecutive_failures = %s
            WHERE source = %s
        ''', ('failed', failures, 'x'))
        conn.commit()
        log.error(f'X ingestion failed: {e}')
        if failures >= 2:
            send_alert(f'🚨 MCC: X ingestion has failed {failures} times in a row.\nError: {e}')
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
