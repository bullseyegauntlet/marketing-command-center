#!/usr/bin/env python3
"""
LinkedIn Mentions Ingestion Pipeline
Fetches posts from Gauntlet AI's LinkedIn company page + configured profile watchlist,
tags them is_mention=True, and inserts into the posts table.
Runs daily via GitHub Actions cron.

Uses linkedin-api 2.3.1 (unofficial Voyager API wrapper).
See: https://github.com/tomquirk/linkedin-api

NOTE: search_posts() was removed in linkedin-api 2.x. We use:
  - api.get_company_updates(public_id) — Gauntlet's own company page
  - api.get_profile_posts(urn_id)      — optional watchlist of individuals

Env vars:
  LINKEDIN_EMAIL                  Bot account email
  LINKEDIN_COOKIES_PATH           Path to JSON file with LinkedIn cookies
  LINKEDIN_COMPANY_IDS            Comma-separated company public IDs (default: gauntletai)
  LINKEDIN_PROFILE_URNS           Comma-separated profile URN IDs to watch (optional)
  DATABASE_URL                    PostgreSQL connection string
  OPENROUTER_API_KEY              For embeddings
  OPENAI_API_KEY                  Fallback for embeddings
  SLACK_BOT_TOKEN                 For error/popular alerts (optional)
  SLACK_ALERT_CHANNEL             Slack channel for alerts (optional)
  POPULAR_THRESHOLD_LI_LIKES      Likes threshold for popular flag (default: 500)
  POPULAR_THRESHOLD_LI_REPOSTS    Shares threshold (default: 100)
  POPULAR_THRESHOLD_LI_REPLIES    Comments threshold (default: 50)

Auth note:
  This bot account (bullseye.gauntlet@gmail.com) was created via Google OAuth — no LinkedIn password.
  Auth uses cookies from LINKEDIN_COOKIES_PATH (~/.openclaw/secrets/linkedin_cookies.json).
  Cookies expire every ~2 weeks. Refresh by running:
    python3 backend/scripts/refresh_linkedin_cookies.py
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from openai import OpenAI
from requests.cookies import RequestsCookieJar

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL          = os.getenv('DATABASE_URL')
LI_EMAIL        = os.getenv('LINKEDIN_EMAIL', 'bullseye.gauntlet@gmail.com')
LI_COOKIES_PATH = os.getenv('LINKEDIN_COOKIES_PATH', os.path.expanduser('~/.openclaw/secrets/linkedin_cookies.json'))
LI_COMPANY_IDS  = [c.strip() for c in os.getenv('LINKEDIN_COMPANY_IDS', 'gauntletai').split(',') if c.strip()]
LI_PROFILE_URNS = [u.strip() for u in os.getenv('LINKEDIN_PROFILE_URNS', '').split(',') if u.strip()]
SLACK_TOKEN     = os.getenv('SLACK_BOT_TOKEN')
ALERT_CHANNEL   = os.getenv('SLACK_ALERT_CHANNEL')

OPENROUTER_API_KEY  = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY      = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY   = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL  = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL     = 'text-embedding-3-small'
DEAD_LETTER_PATH    = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_linkedin.json')

POPULAR_THRESHOLD_LI_LIKES    = int(os.getenv('POPULAR_THRESHOLD_LI_LIKES', 500))
POPULAR_THRESHOLD_LI_REPOSTS  = int(os.getenv('POPULAR_THRESHOLD_LI_REPOSTS', 100))
POPULAR_THRESHOLD_LI_REPLIES  = int(os.getenv('POPULAR_THRESHOLD_LI_REPLIES', 50))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


# ─── Alerts ────────────────────────────────────────────────────────────────────

def send_alert(message: str):
    if not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    try:
        requests.post(
            'https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message},
            timeout=10,
        )
    except Exception as e:
        log.error(f'Failed to send Slack alert: {e}')


def send_popular_alert(post: dict, triggered_by: str, metric_value: int):
    if not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    likes    = post.get('likes', 0)
    reposts  = post.get('retweets', 0)
    replies  = post.get('replies', 0)
    preview  = post.get('content', '')[:200]
    author   = post.get('author', 'unknown')
    url      = post.get('source_url', '')
    threshold_map = {
        'likes': POPULAR_THRESHOLD_LI_LIKES,
        'reposts': POPULAR_THRESHOLD_LI_REPOSTS,
        'replies': POPULAR_THRESHOLD_LI_REPLIES,
    }
    threshold = threshold_map.get(triggered_by, '?')
    message = (
        f'🔥 *Viral LinkedIn Post Detected*\n\n'
        f'*{author}* posted something taking off:\n\n'
        f'> "{preview}"\n\n'
        f'❤ *{likes:,} likes*  🔁 *{reposts:,} shares*  💬 *{replies:,} comments*\n'
        f'📎 {url}\n\n'
        f'_Triggered by: {metric_value:,} {triggered_by} (threshold: {threshold:,})_'
    )
    try:
        requests.post(
            'https://slack.com/api/chat.postMessage',
            headers={'Authorization': f'Bearer {SLACK_TOKEN}'},
            json={'channel': ALERT_CHANNEL, 'text': message},
            timeout=10,
        )
    except Exception as e:
        log.error(f'Failed to send popular alert: {e}')


# ─── Dead Letter ───────────────────────────────────────────────────────────────

def log_dead_letter(post: dict, error: str):
    os.makedirs(os.path.dirname(DEAD_LETTER_PATH), exist_ok=True)
    entry = {'timestamp': datetime.utcnow().isoformat(), 'error': error, 'post': post}
    try:
        with open(DEAD_LETTER_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        log.error(f'Failed to write dead letter: {e}')


# ─── Popularity Check ──────────────────────────────────────────────────────────

def check_popular_thresholds(cur, conn, post_id: str, post: dict):
    likes   = post.get('likes', 0)
    reposts = post.get('retweets', 0)
    replies = post.get('replies', 0)

    triggered_by = None
    metric_value = 0

    if likes >= POPULAR_THRESHOLD_LI_LIKES:
        triggered_by, metric_value = 'likes', likes
    elif reposts >= POPULAR_THRESHOLD_LI_REPOSTS:
        triggered_by, metric_value = 'reposts', reposts
    elif replies >= POPULAR_THRESHOLD_LI_REPLIES:
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
        if cur.rowcount > 0:
            log.info(f'Flagged LinkedIn post {post_id} as popular ({triggered_by}: {metric_value})')
            send_popular_alert(post, triggered_by, metric_value)
    except Exception as e:
        log.error(f'Failed to flag popular LinkedIn post {post_id}: {e}')
        conn.rollback()


# ─── Post Parsing ──────────────────────────────────────────────────────────────

def parse_company_update(raw: dict, company_name: str) -> Optional[dict]:
    """
    Parse a post from get_company_updates().
    Raw structure: { urn, entityUrn, id, permalink, value: { com.linkedin.voyager.feed.render.UpdateV2: {...} } }
    """
    # Activity URN for external_id
    urn = raw.get('urn', '')
    activity_id = urn.split(':')[-1] if urn else None
    if not activity_id:
        return None

    val = raw.get('value', {}).get('com.linkedin.voyager.feed.render.UpdateV2', {})
    if not val:
        return None

    # Text content
    commentary = val.get('commentary', {})
    if isinstance(commentary, dict):
        text_obj = commentary.get('text', {})
        content = text_obj.get('text', '') if isinstance(text_obj, dict) else str(text_obj)
    else:
        content = str(commentary) if commentary else ''

    if not content.strip():
        return None  # skip image/video-only posts

    # Engagement metrics from socialDetail
    social = val.get('socialDetail', {})
    likes   = len(social.get('reactionElements', []))  # reactions shown in preview
    reposts = social.get('totalShares', 0)
    replies = social.get('comments', {}).get('paging', {}).get('total', 0)

    # Permalink from raw
    source_url = raw.get('permalink', f'https://www.linkedin.com/feed/update/{urn}/')

    # Timestamp — not always present; fall back to now
    published_at = datetime.utcnow()

    return {
        'external_id': f'li_{activity_id}',
        'author': company_name,
        'content': content,
        'source_url': source_url,
        'published_at': published_at,
        'likes': likes,
        'retweets': reposts,
        'replies': replies,
        'links': json.dumps([]),
        '_engagement': {'likes': likes, 'retweets': reposts, 'replies': replies},
    }


def parse_profile_post(raw: dict) -> Optional[dict]:
    """
    Parse a post from get_profile_posts().
    Similar structure to company updates but actor is a person.
    """
    urn = raw.get('entityUrn', raw.get('dashEntityUrn', ''))
    activity_id = urn.split(':')[-1] if urn else None
    if not activity_id:
        return None

    val = raw.get('value', {}).get('com.linkedin.voyager.feed.render.UpdateV2', raw)

    commentary = val.get('commentary', {})
    if isinstance(commentary, dict):
        text_obj = commentary.get('text', {})
        content = text_obj.get('text', '') if isinstance(text_obj, dict) else str(text_obj)
    else:
        content = str(commentary) if commentary else ''

    if not content.strip():
        return None

    # Author name
    actor = val.get('actor', {})
    name_obj = actor.get('name', {})
    if isinstance(name_obj, dict):
        author = name_obj.get('text', 'unknown')
    else:
        author = str(name_obj) if name_obj else 'unknown'

    social = val.get('socialDetail', {})
    likes   = len(social.get('reactionElements', []))
    reposts = social.get('totalShares', 0)
    replies = social.get('comments', {}).get('paging', {}).get('total', 0)

    source_url = raw.get('permalink', f'https://www.linkedin.com/feed/update/{urn}/')

    return {
        'external_id': f'li_{activity_id}',
        'author': author,
        'content': content,
        'source_url': source_url,
        'published_at': datetime.utcnow(),
        'likes': likes,
        'retweets': reposts,
        'replies': replies,
        'links': json.dumps([]),
        '_engagement': {'likes': likes, 'retweets': reposts, 'replies': replies},
    }


# ─── Auth ──────────────────────────────────────────────────────────────────────

def load_cookie_jar(cookies_path: str) -> RequestsCookieJar:
    """Load LinkedIn cookies from JSON file into a RequestsCookieJar."""
    with open(cookies_path) as f:
        raw = json.load(f)
    jar = RequestsCookieJar()
    for name, value in raw.items():
        jar.set(name, value, domain='.linkedin.com', path='/')
    return jar


# ─── Embeddings ────────────────────────────────────────────────────────────────

def get_embeddings(client: OpenAI, texts: list) -> list:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ─── Main ──────────────────────────────────────────────────────────────────────

def run():
    if not LI_EMAIL:
        log.error('LINKEDIN_EMAIL must be set.')
        return

    if not LI_COOKIES_PATH or not os.path.exists(LI_COOKIES_PATH):
        log.error(f'LinkedIn cookies not found at {LI_COOKIES_PATH}. Run refresh_linkedin_cookies.py.')
        return

    try:
        from linkedin_api import Linkedin
    except ImportError:
        log.error('linkedin-api not installed. Run: pip install linkedin-api')
        return

    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    cur.execute(
        'SELECT consecutive_failures FROM ingestion_checkpoints WHERE source = %s',
        ('linkedin_mentions',)
    )
    row      = cur.fetchone()
    failures = row['consecutive_failures'] if row else 0

    try:
        # Auth with cookie jar
        log.info(f'Authenticating with LinkedIn via cookies ({LI_COOKIES_PATH})')
        jar = load_cookie_jar(LI_COOKIES_PATH)
        api = Linkedin(LI_EMAIL, '', cookies=jar)

        all_parsed: list = []
        seen_ids: set = set()

        # ── Company page posts ───────────────────────────────────────────────
        for company_id in LI_COMPANY_IDS:
            log.info(f'Fetching company updates for: {company_id}')
            try:
                updates = api.get_company_updates(company_id, max_results=50)
                log.info(f'  → {len(updates)} updates')
                time.sleep(3)
            except Exception as e:
                log.error(f'  Failed to fetch company updates for {company_id}: {e}')
                continue

            for raw in updates:
                parsed = parse_company_update(raw, company_id)
                if not parsed or parsed['external_id'] in seen_ids:
                    continue
                seen_ids.add(parsed['external_id'])
                cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (parsed['external_id'],))
                if not cur.fetchone():
                    all_parsed.append(parsed)

        # ── Profile watchlist posts ──────────────────────────────────────────
        for urn_id in LI_PROFILE_URNS:
            log.info(f'Fetching profile posts for URN: {urn_id}')
            try:
                posts = api.get_profile_posts(urn_id=urn_id, post_count=20)
                log.info(f'  → {len(posts)} posts')
                time.sleep(3)
            except Exception as e:
                log.error(f'  Failed to fetch profile posts for {urn_id}: {e}')
                continue

            for raw in posts:
                parsed = parse_profile_post(raw)
                if not parsed or parsed['external_id'] in seen_ids:
                    continue
                seen_ids.add(parsed['external_id'])
                cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (parsed['external_id'],))
                if not cur.fetchone():
                    all_parsed.append(parsed)

        log.info(f'New LinkedIn posts to insert: {len(all_parsed)}')

        # ── Embed + Insert ───────────────────────────────────────────────────
        if all_parsed:
            BATCH = 50
            for i in range(0, len(all_parsed), BATCH):
                batch = all_parsed[i:i + BATCH]
                texts = [p['content'] for p in batch]
                try:
                    embeddings = get_embeddings(openai_client, texts)
                except Exception as e:
                    log.error(f'Embedding batch failed: {e}')
                    embeddings = [None] * len(batch)

                for post, embedding in zip(batch, embeddings):
                    try:
                        cur.execute('''
                            INSERT INTO posts (
                                platform, external_id, author, content, source_url,
                                published_at, likes, retweets, replies,
                                channel, links, embedding, is_mention
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                            ON CONFLICT (external_id) DO NOTHING
                            RETURNING id
                        ''', (
                            'linkedin',
                            post['external_id'],
                            post['author'],
                            post['content'],
                            post['source_url'],
                            post['published_at'],
                            post['likes'],
                            post['retweets'],
                            post['replies'],
                            'linkedin_mentions',
                            post['links'],
                            embedding,
                        ))
                        inserted_row = cur.fetchone()
                        if inserted_row:
                            check_popular_thresholds(cur, conn, str(inserted_row['id']), post)
                    except Exception as e:
                        log.error(f'Insert failed for {post["external_id"]}: {e}')
                        log_dead_letter(post, str(e))
                        conn.rollback()

                conn.commit()
                log.info(f'Inserted batch {i // BATCH + 1} ({len(batch)} posts)')

        # ── Update Checkpoint ────────────────────────────────────────────────
        cur.execute('''
            INSERT INTO ingestion_checkpoints (source, last_run_at, status, consecutive_failures)
            VALUES (%s, NOW(), 'success', 0)
            ON CONFLICT (source) DO UPDATE
            SET last_run_at = EXCLUDED.last_run_at,
                status = EXCLUDED.status,
                consecutive_failures = 0
        ''', ('linkedin_mentions',))
        conn.commit()
        log.info('LinkedIn mentions ingestion complete.')

    except Exception as e:
        failures += 1
        cur.execute('''
            INSERT INTO ingestion_checkpoints (source, last_run_at, status, consecutive_failures)
            VALUES (%s, NOW(), 'failed', %s)
            ON CONFLICT (source) DO UPDATE
            SET last_run_at = EXCLUDED.last_run_at,
                status = EXCLUDED.status,
                consecutive_failures = EXCLUDED.consecutive_failures
        ''', ('linkedin_mentions', failures))
        conn.commit()
        log.error(f'LinkedIn mentions ingestion failed: {e}')
        if failures >= 2:
            send_alert(
                f'🚨 MCC: LinkedIn mentions ingestion has failed {failures} times in a row.\nError: {e}'
            )
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
