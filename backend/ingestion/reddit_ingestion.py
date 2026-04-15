#!/usr/bin/env python3
"""
Reddit Mentions Ingestion Pipeline
Searches Reddit for posts explicitly mentioning Gauntlet AI.
Runs daily via cron. Tags all posts with is_mention=TRUE.

Only uses Reddit's search API with brand keywords — does NOT scrape subreddits
wholesale. Every post ingested must match a Gauntlet AI keyword.

Auth:
  Works in unauthenticated mode (public API) or authenticated mode (OAuth script app).
  Authenticated mode has higher rate limits (60 req/min vs 10 req/min unauthenticated).

  To enable OAuth:
  1. Create a "script" app at old.reddit.com/prefs/apps
     - Name: MCC-Monitor
     - Type: script
     - Redirect: http://localhost:8080
  2. Add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to .env

Env vars:
  REDDIT_CLIENT_ID          OAuth client_id (optional — falls back to public API)
  REDDIT_CLIENT_SECRET      OAuth client_secret (optional)
  REDDIT_USERNAME           Bot username (default: Bullseye_Gauntlet)
  REDDIT_PASSWORD           Bot password
  REDDIT_SEARCH_QUERIES     Comma-separated search queries (default below)
  DATABASE_URL
  OPENROUTER_API_KEY / OPENAI_API_KEY
  SLACK_BOT_TOKEN
  SLACK_ALERT_CHANNEL
  POPULAR_THRESHOLD_REDDIT_UPVOTES   (default: 100)
  POPULAR_THRESHOLD_REDDIT_COMMENTS  (default: 50)
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

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL              = os.getenv('DATABASE_URL')
REDDIT_CLIENT_ID    = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET= os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USERNAME     = os.getenv('REDDIT_USERNAME', 'Bullseye_Gauntlet')
REDDIT_PASSWORD     = os.getenv('REDDIT_PASSWORD')
SLACK_TOKEN         = os.getenv('SLACK_BOT_TOKEN')
ALERT_CHANNEL       = os.getenv('SLACK_ALERT_CHANNEL')

OPENROUTER_API_KEY  = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY      = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY   = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL  = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL     = 'text-embedding-3-small'

SEARCH_QUERIES_RAW  = os.getenv('REDDIT_SEARCH_QUERIES',
    '"Gauntlet AI",gauntletai,"Gauntlet AI program","gauntletai.com"')
SEARCH_QUERIES      = [q.strip() for q in SEARCH_QUERIES_RAW.split(',') if q.strip()]

POPULAR_THRESHOLD_REDDIT_UPVOTES  = int(os.getenv('POPULAR_THRESHOLD_REDDIT_UPVOTES', 100))
POPULAR_THRESHOLD_REDDIT_COMMENTS = int(os.getenv('POPULAR_THRESHOLD_REDDIT_COMMENTS', 50))

USER_AGENT = f'MCC-Monitor/1.0 by {REDDIT_USERNAME}'
DEAD_LETTER_PATH = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_reddit.json')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

_access_token: Optional[str] = None
_token_expiry: float = 0


def get_access_token() -> Optional[str]:
    """Get OAuth access token if credentials are configured."""
    global _access_token, _token_expiry
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET or not REDDIT_PASSWORD:
        return None
    if _access_token and time.time() < _token_expiry - 60:
        return _access_token
    r = requests.post(
        'https://www.reddit.com/api/v1/access_token',
        auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
        data={'grant_type': 'password', 'username': REDDIT_USERNAME, 'password': REDDIT_PASSWORD},
        headers={'User-Agent': USER_AGENT},
        timeout=15,
    )
    if r.ok:
        data = r.json()
        _access_token = data.get('access_token')
        _token_expiry = time.time() + data.get('expires_in', 3600)
        log.info('Reddit OAuth token obtained')
        return _access_token
    log.warning(f'Reddit OAuth failed ({r.status_code}) — falling back to public API')
    return None


def reddit_get(path: str, params: dict, retries=3) -> Optional[dict]:
    """GET from Reddit API with auth fallback."""
    token = get_access_token()
    if token:
        base = 'https://oauth.reddit.com'
        headers = {'Authorization': f'Bearer {token}', 'User-Agent': USER_AGENT}
    else:
        base = 'https://www.reddit.com'
        if not path.endswith('.json'):
            path = path.rstrip('/') + '.json'
        headers = {'User-Agent': USER_AGENT}

    for attempt in range(retries):
        try:
            r = requests.get(f'{base}{path}', params=params, headers=headers, timeout=15)
            if r.status_code == 429:
                wait = int(r.headers.get('Retry-After', 60))
                log.warning(f'Reddit rate limited, waiting {wait}s')
                time.sleep(wait)
                continue
            if r.ok:
                return r.json()
            log.error(f'Reddit API error {r.status_code}: {r.text[:200]}')
            return None
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f'Request failed (attempt {attempt+1}): {e}. Retrying in {wait}s')
            time.sleep(wait)
    return None


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


def send_popular_alert(post: dict, triggered_by: str, metric_value: int):
    content_preview = post.get('content', '')[:200]
    subreddit = post.get('channel', 'reddit')
    url = post.get('source_url', '')
    upvotes = post.get('likes', 0)
    comments = post.get('replies', 0)
    threshold = POPULAR_THRESHOLD_REDDIT_UPVOTES if triggered_by == 'upvotes' else POPULAR_THRESHOLD_REDDIT_COMMENTS
    message = (
        f'🔥 *Trending Reddit Post Detected*\n\n'
        f'*r/{subreddit}* is blowing up:\n\n'
        f'> "{content_preview}"\n\n'
        f'⬆️ *{upvotes:,} upvotes*  💬 *{comments:,} comments*\n'
        f'📎 {url}\n\n'
        f'_Triggered by: {metric_value:,} {triggered_by} (threshold: {threshold:,})_'
    )
    send_alert(message)


def check_popular_thresholds(cur, conn, post_id: str, post: dict):
    upvotes  = post.get('likes', 0) or 0
    comments = post.get('replies', 0) or 0

    triggered_by = None
    metric_value = 0

    if upvotes >= POPULAR_THRESHOLD_REDDIT_UPVOTES:
        triggered_by, metric_value = 'upvotes', upvotes
    elif comments >= POPULAR_THRESHOLD_REDDIT_COMMENTS:
        triggered_by, metric_value = 'comments', comments

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
            log.info(f'Flagged Reddit post {post_id} as popular ({triggered_by}: {metric_value})')
            send_popular_alert(post, triggered_by, metric_value)
    except Exception as e:
        log.error(f'Failed to flag popular post {post_id}: {e}')
        conn.rollback()


def log_dead_letter(post: dict, error: str):
    os.makedirs(os.path.dirname(DEAD_LETTER_PATH), exist_ok=True)
    entry = {'timestamp': datetime.utcnow().isoformat(), 'error': error, 'post': post}
    try:
        with open(DEAD_LETTER_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        log.error(f'Failed to write dead letter: {e}')


def extract_posts_from_listing(data: dict) -> list:
    """Extract post dicts from a Reddit listing response."""
    if not data:
        return []
    children = data.get('data', {}).get('children', [])
    return [c['data'] for c in children if c.get('kind') == 't3']


def normalize_post(post_data: dict, query: str = '') -> Optional[dict]:
    """Normalize a Reddit post into MCC post format."""
    post_id = post_data.get('id', '')
    if not post_id:
        return None

    title   = post_data.get('title', '')
    selftext = post_data.get('selftext', '')
    content = f"{title}\n\n{selftext}".strip() if selftext and selftext != '[removed]' else title
    author  = post_data.get('author', '[deleted]')
    subreddit = post_data.get('subreddit', '')
    permalink = post_data.get('permalink', '')
    url     = post_data.get('url', '')
    created = post_data.get('created_utc', 0)
    upvotes = post_data.get('score', 0)
    num_comments = post_data.get('num_comments', 0)

    source_url = f'https://www.reddit.com{permalink}' if permalink else url
    published_at = datetime.fromtimestamp(created, tz=timezone.utc).replace(tzinfo=None)
    external_id = f'reddit_{post_id}'

    # Extract links from selftext
    import re
    links = re.findall(r'https?://[^\s\)\"]+', selftext or '')
    if url and not url.startswith('https://www.reddit.com'):
        links.append(url)

    return {
        'external_id': external_id,
        'author': author,
        'content': content,
        'source_url': source_url,
        'published_at': published_at,
        'likes': upvotes,
        'replies': num_comments,
        'channel': subreddit,
        'links': json.dumps(list(set(links))),
        '_upvotes': upvotes,
        '_comments': num_comments,
    }


def search_reddit(query: str, since_ts: Optional[float] = None) -> list:
    """Search Reddit for posts matching query."""
    params = {
        'q': query,
        'sort': 'new',
        'limit': 100,
        't': 'month',
        'type': 'link',
    }
    data = reddit_get('/search', params)
    if not data:
        return []

    posts = extract_posts_from_listing(data)

    # Filter to posts newer than checkpoint
    if since_ts:
        posts = [p for p in posts if p.get('created_utc', 0) > since_ts]

    return [normalize_post(p, query) for p in posts if normalize_post(p, query)]



def insert_posts(cur, conn, openai_client, posts: list, is_mention: bool = False):
    """Deduplicate, embed, and insert a list of normalized posts."""
    # Deduplicate against DB
    new_posts = []
    for post in posts:
        cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (post['external_id'],))
        if not cur.fetchone():
            new_posts.append(post)

    if not new_posts:
        return 0

    # Generate embeddings
    BATCH = 50
    inserted = 0
    for i in range(0, len(new_posts), BATCH):
        batch = new_posts[i:i+BATCH]
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
                        published_at, likes, replies, channel, links, embedding, is_mention)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_id) DO NOTHING
                    RETURNING id
                ''', (
                    'reddit', post['external_id'], post['author'], post['content'],
                    post['source_url'], post['published_at'],
                    post.get('likes', 0), post.get('replies', 0),
                    post.get('channel', ''), post.get('links', '[]'),
                    embedding, is_mention
                ))
                row = cur.fetchone()
                if row:
                    inserted += 1
                    check_popular_thresholds(cur, conn, str(row['id']), post)
            except Exception as e:
                log.error(f'Insert failed for {post["external_id"]}: {e}')
                log_dead_letter(post, str(e))
                conn.rollback()

        conn.commit()

    return inserted


def run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    # Get checkpoint
    cur.execute("SELECT last_id FROM ingestion_checkpoints WHERE source = 'reddit'")
    row = cur.fetchone()
    since_ts = float(row['last_id']) if row and row['last_id'] else None
    latest_ts = since_ts

    total_inserted = 0

    try:
        # 1. Keyword searches (brand mentions)
        seen_ids: set = set()
        mention_posts = []
        for query in SEARCH_QUERIES:
            log.info(f'Searching Reddit for: {query}')
            posts = search_reddit(query, since_ts)
            for p in posts:
                if p['external_id'] not in seen_ids:
                    seen_ids.add(p['external_id'])
                    mention_posts.append(p)
                    ts = p['published_at'].timestamp()
                    if not latest_ts or ts > latest_ts:
                        latest_ts = ts
            time.sleep(1)  # respect rate limits

        log.info(f'Found {len(mention_posts)} mention posts across all queries')
        n = insert_posts(cur, conn, openai_client, mention_posts, is_mention=True)
        total_inserted += n
        log.info(f'Inserted {n} new mention posts')

        # Update checkpoint
        if latest_ts:
            cur.execute('''
                INSERT INTO ingestion_checkpoints (source, last_id, last_run_at, status, consecutive_failures)
                VALUES ('reddit', %s, NOW(), 'success', 0)
                ON CONFLICT (source) DO UPDATE
                SET last_id = EXCLUDED.last_id, last_run_at = NOW(),
                    status = 'success', consecutive_failures = 0
            ''', (str(latest_ts),))
            conn.commit()

        log.info(f'Reddit ingestion complete: {total_inserted} new posts total')

    except Exception as e:
        log.error(f'Reddit ingestion failed: {e}')
        cur.execute('''
            INSERT INTO ingestion_checkpoints (source, last_id, last_run_at, status, consecutive_failures)
            VALUES ('reddit', %s, NOW(), 'failed', 1)
            ON CONFLICT (source) DO UPDATE
            SET last_run_at = NOW(), status = 'failed',
                consecutive_failures = ingestion_checkpoints.consecutive_failures + 1
        ''', (str(since_ts or ''),))
        conn.commit()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
