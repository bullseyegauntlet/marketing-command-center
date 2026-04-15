#!/usr/bin/env python3
"""
LinkedIn Mentions Ingestion Pipeline
Searches LinkedIn for posts mentioning Gauntlet AI and inserts into the posts table.

Uses linkedin-api (unofficial Voyager API wrapper). Requires a dedicated bot account.
See: https://github.com/tomquirk/linkedin-api

Env vars:
  LINKEDIN_EMAIL             Bot account email
  LINKEDIN_PASSWORD          Bot account password
  LINKEDIN_MENTION_KEYWORDS  Comma-separated keywords (default: "Gauntlet AI,gauntletai")
  DATABASE_URL               PostgreSQL connection string
  OPENROUTER_API_KEY         For embeddings
  OPENAI_API_KEY             Fallback for embeddings
  SLACK_BOT_TOKEN            For error alerts (optional)
  SLACK_ALERT_CHANNEL        Slack channel for error alerts (optional)
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

DB_URL = os.getenv('DATABASE_URL')
LI_EMAIL = os.getenv('LINKEDIN_EMAIL')
LI_PASSWORD = os.getenv('LINKEDIN_PASSWORD')
LI_KEYWORDS_RAW = os.getenv('LINKEDIN_MENTION_KEYWORDS', 'Gauntlet AI,gauntletai')
LI_KEYWORDS = [k.strip() for k in LI_KEYWORDS_RAW.split(',') if k.strip()]
SLACK_TOKEN = os.getenv('SLACK_BOT_TOKEN')
ALERT_CHANNEL = os.getenv('SLACK_ALERT_CHANNEL')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL = 'text-embedding-3-small'
DEAD_LETTER_PATH = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_linkedin.json')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


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


def log_dead_letter(post: dict, error: str):
    os.makedirs(os.path.dirname(DEAD_LETTER_PATH), exist_ok=True)
    entry = {'timestamp': datetime.utcnow().isoformat(), 'error': error, 'post': post}
    try:
        with open(DEAD_LETTER_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        log.error(f'Failed to write dead letter: {e}')


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
    # Article attachments
    article = post.get('content', {}).get('article', {})
    resolved = article.get('source', {}).get('resolvedUrl', '')
    if resolved:
        links.append(resolved)
    # Multi-image links (uncommon but possible)
    for img in post.get('content', {}).get('multiImage', {}).get('images', []):
        url = img.get('url', '')
        if url:
            links.append(url)
    return links


def get_author_name(post: dict) -> str:
    """Extract a readable author name from the post object."""
    actor = post.get('actor', {})
    # Person
    name_obj = actor.get('name', {})
    if isinstance(name_obj, dict):
        first = name_obj.get('firstName', {})
        last = name_obj.get('lastName', {})
        first_str = first.get('text', '') if isinstance(first, dict) else str(first)
        last_str = last.get('text', '') if isinstance(last, dict) else str(last)
        full = f'{first_str} {last_str}'.strip()
        if full:
            return full
    # Company / org
    title = actor.get('title', {})
    if isinstance(title, dict):
        t = title.get('text', '')
        if t:
            return t
    # Fallback to URN
    urn = post.get('actor', {}).get('urn', post.get('dashEntityUrn', 'unknown'))
    return urn.split(':')[-1] if urn else 'unknown'


def parse_post(post: dict) -> Optional[dict]:
    """Normalize a raw LinkedIn post to MCC schema."""
    urn = post.get('entityUrn', post.get('dashEntityUrn', ''))
    activity_id = urn.split(':')[-1] if urn else None
    if not activity_id:
        return None

    content = get_post_text(post)
    if not content.strip():
        return None  # Skip image-only / video-only posts

    social = post.get('socialDetail', {}).get('totalSocialActivityCounts', {})
    created_ms = post.get('created', {}).get('time', 0)
    published_at = datetime.utcfromtimestamp(created_ms / 1000) if created_ms else datetime.utcnow()

    source_url = f'https://www.linkedin.com/feed/update/{urn}/'
    links = extract_links(post)
    author = get_author_name(post)

    return {
        'external_id': f'li_{activity_id}',
        'author': author,
        'content': content,
        'source_url': source_url,
        'published_at': published_at,
        'likes': social.get('numLikes', 0),
        'retweets': social.get('numShares', 0),
        'replies': social.get('numComments', 0),
        'links': json.dumps(links),
    }


def get_embeddings(client: OpenAI, texts: list) -> list:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def run():
    if not LI_EMAIL or not LI_PASSWORD:
        log.error('LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set.')
        return

    try:
        from linkedin_api import Linkedin
    except ImportError:
        log.error('linkedin-api not installed. Run: pip install linkedin-api')
        return

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    cur.execute(
        'SELECT consecutive_failures FROM ingestion_checkpoints WHERE source = %s',
        ('linkedin_mentions',)
    )
    row = cur.fetchone()
    failures = row['consecutive_failures'] if row else 0

    try:
        log.info(f'Authenticating with LinkedIn as {LI_EMAIL}')
        api = Linkedin(LI_EMAIL, LI_PASSWORD)

        all_parsed = []
        seen_ids = set()

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

                # Skip if already in DB
                cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (parsed['external_id'],))
                if cur.fetchone():
                    continue

                all_parsed.append(parsed)

        log.info(f'New posts to insert: {len(all_parsed)}')

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
                    except Exception as e:
                        log.error(f'Insert failed for {post["external_id"]}: {e}')
                        log_dead_letter(post, str(e))
                        conn.rollback()

                conn.commit()
                log.info(f'Inserted batch {i // BATCH + 1} ({len(batch)} posts)')

        # Update checkpoint
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
