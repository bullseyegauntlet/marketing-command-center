#!/usr/bin/env python3
"""
Slack Ingestion Pipeline
Fetches messages from configured channels and inserts into posts table.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL = os.getenv('DATABASE_URL')
SLACK_TOKEN = os.getenv('SLACK_BOT_TOKEN')
CHANNEL_IDS = [c.strip() for c in os.getenv('SLACK_CHANNEL_IDS', '').split(',') if c.strip()]
ALERT_CHANNEL = os.getenv('SLACK_ALERT_CHANNEL')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL = 'text-embedding-3-small'
DEAD_LETTER_PATH = os.path.join(os.path.dirname(__file__), '../logs/dead_letter.json')

# Popular post threshold
POPULAR_THRESHOLD_SLACK_REPLIES = int(os.getenv('POPULAR_THRESHOLD_SLACK_REPLIES', 20))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


def slack_get(endpoint: str, params: dict, retries=3) -> dict:
    """Call Slack API with retry/backoff."""
    headers = {'Authorization': f'Bearer {SLACK_TOKEN}'}
    for attempt in range(retries):
        try:
            r = requests.get(f'https://slack.com/api/{endpoint}', headers=headers, params=params, timeout=15)
            data = r.json()
            if data.get('ok'):
                return data
            if data.get('error') == 'ratelimited':
                wait = int(r.headers.get('Retry-After', 5))
                log.warning(f'Rate limited, waiting {wait}s')
                time.sleep(wait)
                continue
            log.error(f'Slack API error: {data.get("error")}')
            return data
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f'Request failed (attempt {attempt+1}): {e}. Retrying in {wait}s')
            time.sleep(wait)
    return {'ok': False, 'error': 'max_retries_exceeded'}


def extract_links(text: str) -> list:
    return re.findall(r'https?://[^\s<>\"]+', text or '')


def ts_to_datetime(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)


def build_source_url(channel_id: str, ts: str) -> str:
    ts_clean = ts.replace('.', '')
    return f'https://gauntlet-ai.slack.com/archives/{channel_id}/p{ts_clean}'


def get_embeddings(client: OpenAI, texts: list) -> list:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def send_popular_alert(channel_id: str, content_preview: str, reply_count: int, source_url: str):
    """Send a Slack alert for a hot Slack thread."""
    if not ALERT_CHANNEL:
        return
    channel_display = f'#{channel_id}' if not channel_id.startswith('#') else channel_id
    message = (
        f'🔥 *Hot Slack Thread Detected*\n\n'
        f'*{channel_display}* thread is blowing up:\n\n'
        f'> "{content_preview[:200]}"\n\n'
        f'💬 *{reply_count} replies*\n'
        f'📎 {source_url}\n\n'
        f'_Triggered by: {reply_count} thread replies (threshold: {POPULAR_THRESHOLD_SLACK_REPLIES})_'
    )
    try:
        requests.post('https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)
    except Exception as e:
        log.error(f'Failed to send popular alert: {e}')


def check_slack_popular(cur, conn, post_id: str, reply_count: int,
                        channel_id: str, content: str, source_url: str):
    """Flag a Slack thread as popular if reply_count exceeds threshold."""
    if reply_count < POPULAR_THRESHOLD_SLACK_REPLIES:
        return
    try:
        cur.execute('''
            INSERT INTO popular_posts (post_id, triggered_by, metric_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (post_id) DO NOTHING
        ''', (post_id, 'slack_thread_replies', reply_count))
        conn.commit()
        log.info(f'Flagged Slack post {post_id} as popular ({reply_count} replies)')
        send_popular_alert(channel_id, content, reply_count, source_url)
    except Exception as e:
        log.error(f'Failed to flag popular Slack post {post_id}: {e}')
        conn.rollback()


def send_alert(message: str):
    if not ALERT_CHANNEL:
        return
    requests.post('https://slack.com/api/chat.postMessage',
        headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
        json={'channel': ALERT_CHANNEL, 'text': message}, timeout=10)


def log_dead_letter(message: dict, error: str):
    os.makedirs(os.path.dirname(DEAD_LETTER_PATH), exist_ok=True)
    entry = {'timestamp': datetime.utcnow().isoformat(), 'error': error, 'message': message}
    try:
        with open(DEAD_LETTER_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        log.error(f'Failed to write dead letter: {e}')


def get_checkpoint(cur, source: str) -> Optional[str]:
    cur.execute('SELECT last_id FROM ingestion_checkpoints WHERE source = %s', (source,))
    row = cur.fetchone()
    return row[0] if row else None


def update_checkpoint(cur, source: str, last_id: str, status: str, failures: int):
    cur.execute('''
        UPDATE ingestion_checkpoints
        SET last_id = %s, last_run_at = NOW(), status = %s, consecutive_failures = %s
        WHERE source = %s
    ''', (last_id, status, failures, source))


def fetch_channel_messages(channel_id: str, oldest: Optional[str] = None) -> list:
    """Fetch all messages from a channel since oldest ts."""
    messages = []
    params = {'channel': channel_id, 'limit': 200}
    if oldest:
        params['oldest'] = oldest

    while True:
        data = slack_get('conversations.history', params)
        if not data.get('ok'):
            log.error(f'Failed to fetch history for {channel_id}: {data.get("error")}')
            break
        msgs = data.get('messages', [])
        messages.extend(msgs)

        # Fetch thread replies for threaded messages
        for msg in msgs:
            if msg.get('reply_count', 0) > 0 and msg.get('thread_ts') == msg.get('ts'):
                thread_data = slack_get('conversations.replies',
                    {'channel': channel_id, 'ts': msg['ts'], 'limit': 200})
                if thread_data.get('ok'):
                    replies = thread_data.get('messages', [])[1:]  # skip parent
                    messages.extend(replies)

        if not data.get('has_more'):
            break
        params['cursor'] = data['response_metadata']['next_cursor']

    return messages


def ingest_channel(cur, conn, openai_client: OpenAI, channel_id: str, oldest_ts: Optional[str]):
    log.info(f'Fetching messages from channel {channel_id} (oldest: {oldest_ts})')
    messages = fetch_channel_messages(channel_id, oldest_ts)
    log.info(f'  Fetched {len(messages)} messages')

    new_posts = []
    latest_ts = oldest_ts

    for msg in messages:
        ts = msg.get('ts', '')
        if not ts:
            continue

        # Track latest ts for checkpoint
        if not latest_ts or float(ts) > float(latest_ts):
            latest_ts = ts

        # Check for duplicate
        cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (ts,))
        if cur.fetchone():
            continue

        content = msg.get('text', '')
        author = msg.get('user', msg.get('username', 'unknown'))
        source_url = build_source_url(channel_id, ts)
        published_at = ts_to_datetime(ts)
        links = extract_links(content)
        # reply_count is on parent messages from conversations.history
        reply_count = msg.get('reply_count', 0)

        new_posts.append({
            'external_id': ts,
            'author': author,
            'content': content,
            'source_url': source_url,
            'published_at': published_at,
            'channel': channel_id,
            'links': json.dumps(links),
            '_reply_count': reply_count,
        })

    if not new_posts:
        log.info(f'  No new posts for {channel_id}')
        return latest_ts

    # Generate embeddings in batches
    BATCH = 50
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
                        published_at, channel, links, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_id) DO NOTHING
                    RETURNING id
                ''', (
                    'slack', post['external_id'], post['author'], post['content'],
                    post['source_url'], post['published_at'], post['channel'],
                    post['links'], embedding
                ))
                row = cur.fetchone()
                if row and post.get('_reply_count', 0) > 0:
                    check_slack_popular(
                        cur, conn, str(row['id']),
                        post['_reply_count'], post['channel'],
                        post['content'], post['source_url']
                    )
            except Exception as e:
                log.error(f'Insert failed for {post["external_id"]}: {e}')
                log_dead_letter(post, str(e))
                conn.rollback()

        conn.commit()
        log.info(f'  Inserted batch {i//BATCH + 1} ({len(batch)} posts)')

    log.info(f'  Done: {len(new_posts)} new posts for {channel_id}')
    return latest_ts


def run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    # Get checkpoint
    cur.execute('SELECT last_id, consecutive_failures FROM ingestion_checkpoints WHERE source = %s', ('slack',))
    row = cur.fetchone()
    oldest_ts = row['last_id'] if row else None
    failures = row['consecutive_failures'] if row else 0

    try:
        latest_ts = oldest_ts
        for channel_id in CHANNEL_IDS:
            channel_latest = ingest_channel(cur, conn, openai_client, channel_id, oldest_ts)
            if channel_latest and (not latest_ts or float(channel_latest) > float(latest_ts or 0)):
                latest_ts = channel_latest

        update_checkpoint(cur, 'slack', latest_ts, 'success', 0)
        conn.commit()
        log.info('Slack ingestion complete.')

    except Exception as e:
        failures += 1
        update_checkpoint(cur, 'slack', oldest_ts, 'failed', failures)
        conn.commit()
        log.error(f'Slack ingestion failed: {e}')
        if failures >= 2:
            send_alert(f'🚨 MCC: Slack ingestion has failed {failures} times in a row.\nError: {e}')
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
