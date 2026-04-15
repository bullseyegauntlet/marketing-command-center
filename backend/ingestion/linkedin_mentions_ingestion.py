#!/usr/bin/env python3
"""
LinkedIn Mentions Ingestion Pipeline
Searches LinkedIn for posts mentioning Gauntlet AI and inserts into the posts table.
Runs daily via GitHub Actions cron.

Uses linkedin-api (unofficial Voyager API wrapper). Requires a dedicated bot account.
See: https://github.com/tomquirk/linkedin-api

Env vars:
  LINKEDIN_EMAIL                  Bot account email (used with password auth)
  LINKEDIN_PASSWORD               Bot account password (optional if using cookie auth)
  LINKEDIN_COOKIES_PATH           Path to JSON file with LinkedIn cookies (preferred for Google SSO accounts)
  LINKEDIN_MENTION_KEYWORDS       Comma-separated keywords (default: "Gauntlet AI,gauntletai")
  DATABASE_URL                    PostgreSQL connection string
  OPENROUTER_API_KEY              For embeddings
  OPENAI_API_KEY                  Fallback for embeddings
  SLACK_BOT_TOKEN                 For error alerts + popular post alerts (optional)
  SLACK_ALERT_CHANNEL             Slack channel for alerts (optional)
  POPULAR_THRESHOLD_LI_LIKES      Likes threshold for popular flag (default: 500)
  POPULAR_THRESHOLD_LI_REPOSTS    Reposts/shares threshold (default: 100)
  POPULAR_THRESHOLD_LI_REPLIES    Comments threshold (default: 50)

Auth note:
  This bot account (bullseye.gauntlet@gmail.com) was created via Google OAuth — no LinkedIn password.
  Auth uses cookies from LINKEDIN_COOKIES_PATH (~/.openclaw/secrets/linkedin_cookies.json).
  Cookies expire every ~2 weeks. Refresh by logging in via browser and running:
    openclaw browser cookies --browser-profile openclaw | python3 -c "
      import sys,json; c=json.load(sys.stdin)
      li={x['name']:x['value'] for x in c if 'linkedin' in x.get('domain','')}
      open('/Users/bullseye/.openclaw/secrets/linkedin_cookies.json','w').write(json.dumps(li,indent=2))"
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

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL          = os.getenv('DATABASE_URL')
LI_EMAIL        = os.getenv('LINKEDIN_EMAIL', 'bullseye.gauntlet@gmail.com')
LI_PASSWORD     = os.getenv('LINKEDIN_PASSWORD')
LI_COOKIES_PATH = os.getenv('LINKEDIN_COOKIES_PATH', os.path.expanduser('~/.openclaw/secrets/linkedin_cookies.json'))
LI_KEYWORDS_RAW = os.getenv('LINKEDIN_MENTION_KEYWORDS', 'Gauntlet AI,gauntletai')
LI_KEYWORDS     = [k.strip() for k in LI_KEYWORDS_RAW.split(',') if k.strip()]
SLACK_TOKEN     = os.getenv('SLACK_BOT_TOKEN')
ALERT_CHANNEL   = os.getenv('SLACK_ALERT_CHANNEL')

OPENROUTER_API_KEY  = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY      = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY   = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL  = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL     = 'text-embedding-3-small'
DEAD_LETTER_PATH    = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_linkedin.json')

# Popularity thresholds — LinkedIn engagement is lower volume than X so thresholds are lower
POPULAR_THRESHOLD_LI_LIKES    = int(os.getenv('POPULAR_THRESHOLD_LI_LIKES', 500))
POPULAR_THRESHOLD_LI_REPOSTS  = int(os.getenv('POPULAR_THRESHOLD_LI_REPOSTS', 100))
POPULAR_THRESHOLD_LI_REPLIES  = int(os.getenv('POPULAR_THRESHOLD_LI_REPLIES', 50))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


# ─── Alerts ────────────────────────────────────────────────────────────────────

def send_alert(message: str):
    """Send a generic Slack alert (used for ingestion errors)."""
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
    """Send a #bullseye_comms alert for a newly popular LinkedIn post."""
    if not ALERT_CHANNEL or not SLACK_TOKEN:
        return
    likes    = post.get('likes', 0)
    reposts  = post.get('retweets', 0)
    replies  = post.get('replies', 0)
    preview  = post.get('content', '')[:200]
    author   = post.get('author', 'unknown')
    url      = post.get('source_url', '')

    threshold_map = {
        'likes':   POPULAR_THRESHOLD_LI_LIKES,
        'reposts': POPULAR_THRESHOLD_LI_REPOSTS,
        'replies': POPULAR_THRESHOLD_LI_REPLIES,
    }
    threshold = threshold_map.get(triggered_by, '?')

    message = (
        f'🔥 *Viral LinkedIn Post Detected*\n\n'
        f'*{author}* posted something taking off:\n\n'
        f'> "{preview}"\n\n'
        f'❤ *{likes:,} likes*  🔁 *{reposts:,} reposts*  💬 *{replies:,} comments*\n'
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
    """
    Check if a LinkedIn post crosses any popularity threshold.
    If so, insert into popular_posts and fire a Slack alert.
    Mirrors the pattern in x_ingestion.py.
    """
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

def get_post_text(post: dict) -> str:
    """Extract plain text from a LinkedIn post object."""
    commentary = post.get('commentary', {})
    if isinstance(commentary, dict):
        text = commentary.get('text', {})
        if isinstance(text, dict):
            return text.get('text', '')
        return str(text) if text else ''
    return str(commentary) if commentary else ''


def extract_links(post: dict) -> list:
    """Pull any embedded URLs out of a post."""
    links = []
    article = post.get('content', {}).get('article', {})
    resolved = article.get('source', {}).get('resolvedUrl', '')
    if resolved:
        links.append(resolved)
    for img in post.get('content', {}).get('multiImage', {}).get('images', []):
        url = img.get('url', '')
        if url:
            links.append(url)
    return links


def get_author_name(post: dict) -> str:
    """Extract a readable author name from the post object."""
    actor = post.get('actor', {})
    name_obj = actor.get('name', {})
    if isinstance(name_obj, dict):
        first = name_obj.get('firstName', {})
        last  = name_obj.get('lastName', {})
        first_str = first.get('text', '') if isinstance(first, dict) else str(first)
        last_str  = last.get('text', '')  if isinstance(last, dict)  else str(last)
        full = f'{first_str} {last_str}'.strip()
        if full:
            return full
    title = actor.get('title', {})
    if isinstance(title, dict):
        t = title.get('text', '')
        if t:
            return t
    urn = post.get('actor', {}).get('urn', post.get('dashEntityUrn', 'unknown'))
    return urn.split(':')[-1] if urn else 'unknown'


def parse_post(post: dict) -> Optional[dict]:
    """Normalize a raw LinkedIn post to MCC posts schema."""
    urn = post.get('entityUrn', post.get('dashEntityUrn', ''))
    activity_id = urn.split(':')[-1] if urn else None
    if not activity_id:
        return None

    content = get_post_text(post)
    if not content.strip():
        return None  # skip image-only / video-only posts

    social      = post.get('socialDetail', {}).get('totalSocialActivityCounts', {})
    created_ms  = post.get('created', {}).get('time', 0)
    published_at = datetime.utcfromtimestamp(created_ms / 1000) if created_ms else datetime.utcnow()
    source_url  = f'https://www.linkedin.com/feed/update/{urn}/'
    links       = extract_links(post)
    author      = get_author_name(post)

    return {
        'external_id': f'li_{activity_id}',
        'author':      author,
        'content':     content,
        'source_url':  source_url,
        'published_at': published_at,
        'likes':    social.get('numLikes', 0),
        'retweets': social.get('numShares', 0),   # shares → retweets column
        'replies':  social.get('numComments', 0),
        'links':    json.dumps(links),
    }


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
        # ── Auth ────────────────────────────────────────────────────────────────
        if LI_COOKIES_PATH and os.path.exists(LI_COOKIES_PATH):
            log.info(f'Authenticating with LinkedIn via cookies ({LI_COOKIES_PATH})')
            with open(LI_COOKIES_PATH) as f:
                cookies = json.load(f)
            api = Linkedin(LI_EMAIL, '', cookies=cookies)
        elif LI_EMAIL and LI_PASSWORD:
            log.info(f'Authenticating with LinkedIn via email/password as {LI_EMAIL}')
            api = Linkedin(LI_EMAIL, LI_PASSWORD)
        else:
            log.error('No LinkedIn auth method available. Set LINKEDIN_COOKIES_PATH or LINKEDIN_EMAIL+LINKEDIN_PASSWORD.')
            return

        # ── Keyword Search ──────────────────────────────────────────────────────
        all_parsed = []
        seen_ids   = set()

        for keyword in LI_KEYWORDS:
            log.info(f'Searching LinkedIn for: "{keyword}"')
            try:
                results = api.search_posts(keywords=keyword, limit=50)
                log.info(f'  → {len(results)} results')
                time.sleep(3)  # polite delay between keyword searches
            except Exception as e:
                log.error(f'  search failed for "{keyword}": {e}')
                continue

            for post in results:
                parsed = parse_post(post)
                if not parsed:
                    continue
                if parsed['external_id'] in seen_ids:
                    continue  # deduplicate across keyword runs
                seen_ids.add(parsed['external_id'])

                # DB dedup check
                cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (parsed['external_id'],))
                if cur.fetchone():
                    continue

                all_parsed.append(parsed)

        log.info(f'New posts to insert: {len(all_parsed)}')

        # ── Embed + Insert ──────────────────────────────────────────────────────
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
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                            True,   # is_mention = True for all mention-search results
                        ))
                        row = cur.fetchone()
                        if row:
                            # New post — check popularity thresholds (same pattern as x_ingestion)
                            check_popular_thresholds(cur, conn, str(row['id']), post)
                    except Exception as e:
                        log.error(f'Insert failed for {post["external_id"]}: {e}')
                        log_dead_letter(post, str(e))
                        conn.rollback()

                conn.commit()
                log.info(f'Inserted batch {i // BATCH + 1} ({len(batch)} posts)')

        # ── Update Checkpoint ───────────────────────────────────────────────────
        cur.execute('''
            UPDATE ingestion_checkpoints
            SET last_run_at = NOW(), status = 'success', consecutive_failures = 0
            WHERE source = 'linkedin_mentions'
        ''')
        conn.commit()
        log.info('LinkedIn mentions ingestion complete.')

    except Exception as e:
        failures += 1
        cur.execute('''
            UPDATE ingestion_checkpoints
            SET last_run_at = NOW(), status = 'failed', consecutive_failures = %s
            WHERE source = 'linkedin_mentions'
        ''', (failures,))
        conn.commit()
        log.error(f'LinkedIn mentions ingestion failed: {e}')
        if failures >= 2:
            send_alert(f'🚨 MCC: LinkedIn mentions ingestion has failed {failures} times in a row.\nError: {e}')
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run()
