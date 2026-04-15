# LinkedIn Ingestion — Research Report
_Generated: 2026-04-14_

---

## 1. Official LinkedIn API

### What's actually available
LinkedIn's API v2 is heavily restricted. The useful endpoints fall into two tiers:

**Open to any approved app (Community Management API):**
- `GET /ugcPosts` — fetch UGC posts *by the authenticated user* or posts where the org is the author
- `GET /shares` — legacy shares endpoint, mostly deprecated
- `GET /organizationAcls` + `GET /organizationalEntityFeed` — company page posts if you're an admin of the page

**Requires special program access (Marketing Developer Platform / Partner Program):**
- `GET /socialActions/{postUrn}/likes` / `comments` — engagement data
- `GET /feedDistribution` — not public
- Monitoring third-party profiles → **not available at any tier without partnership approval**

### Can you fetch posts from arbitrary people or companies?
**No.** The API cannot fetch posts from a person's profile unless you are that person (or have their delegated OAuth token). For company pages you must be a page admin. There's no equivalent to X's list tweets endpoint.

### OAuth scopes needed
- `r_liteprofile`, `r_emailaddress` — basic profile
- `w_member_social`, `r_member_social` — post/read your own content
- `rw_organization_admin` — company page management (requires verified business)
- `r_organization_social` — read company page posts

### Partner requirements
Getting beyond basic "post as yourself" requires applying for the LinkedIn Marketing Developer Platform partner program. Approval takes weeks to months and requires a legitimate product use case. Internal tooling almost certainly won't qualify.

### Verdict: ❌ Not viable
The official API can't fetch posts from arbitrary profiles/companies. Unless we want to monitor only Gauntlet's own LinkedIn company page posts (we're the admin), the official API is a dead end for the MCC use case.

---

## 2. Unofficial / Scraping Options

### `linkedin-api` (Python)
- **GitHub:** https://github.com/tomquirk/linkedin-api
- **Version:** 2.3.1 (already installed in the system Python env — check MCC venv)
- **Stars:** ~4,000+ — most popular Python LinkedIn scraper
- **How it works:** Authenticates with your LinkedIn credentials (email + password), then reverse-engineers LinkedIn's internal Voyager API (the same JSON API the LinkedIn web app uses). Cookie-based session management after first auth.
- **Can fetch:**
  - Profile posts: `api.get_profile_posts(urn_id)` → returns a feed of posts from a given profile
  - Company updates: `api.get_company_updates(public_id)` → posts from a company page
  - Post reactions/comments counts — available in response data
  - Profiles, connections, search results
- **Stability:** Semi-stable. LinkedIn rotates their internal API endpoints every few months; the library maintainer usually patches within days to weeks. Has broken ~3-4 times in 2024-2025.
- **Auth:** LinkedIn credentials (email + password). Stores cookies after first login. Can also accept pre-extracted cookies.
- **Rate limits:** No hard documented limits but LinkedIn's anti-scraping is aggressive. Recommend: max 100-200 posts/day per account, randomize delays (2-5s between requests), use a dedicated "bot" LinkedIn account (not your personal one).
- **ToS risk:** Violates LinkedIn's User Agreement. LinkedIn has pursued legal action against scrapers (hiQ Labs case). For internal tooling at low volume, enforcement risk is low but not zero. **Do not use a personal or executive's LinkedIn account.**

### Playwright/Selenium approaches
- Fully headless browser scraping
- More resilient to API changes but much slower and heavier
- Not worth it when `linkedin-api` works — save this as fallback
- Libraries: `playwright`, `selenium`, `nodriver` (anti-detection Chromium)

### `linkedin_scraper` (Python)
- **GitHub:** https://github.com/joeyism/linkedin_scraper  
- Selenium-based, profile scraping only
- Less capable than `linkedin-api` for feed/post content
- **Verdict:** Skip — `linkedin-api` is strictly better

### Stability summary
`linkedin-api` is the practical choice. Use a dedicated throw-away LinkedIn account. Accept that it may break occasionally and plan for a patching cycle.

---

## 3. Third-Party Data Providers

### Proxycurl
- **URL:** https://nubela.co/proxycurl
- **What it does:** REST API wrapper around LinkedIn data — profiles, company pages, posts
- **Post endpoint:** `GET /api/linkedin/person/posts` (person) and `GET /api/linkedin/company/posts` (company)
- **Returns:** Post text, timestamp, like count, comment count, post URL, author info
- **Pricing:** ~$0.015–$0.03 per API call (credit-based). $30/mo entry plan = ~1,000–2,000 post fetches. Gets expensive at scale.
- **Fit for MCC:** Good API design that maps cleanly to MCC's schema. Would need to maintain a list of LinkedIn profile URLs to poll. No cookie/auth headaches — just a REST API key.
- **Verdict:** ✅ Best "commercial safe" option if budget allows

### Apify
- **URL:** https://apify.com/actors → search "LinkedIn"
- **Popular actors:** `apify/linkedin-profile-scraper`, `bebity/linkedin-posts-scraper`
- **What it does:** Managed scraping runs — you pass a list of LinkedIn profile URLs, it returns posts
- **Pricing:** Pay-per-run, roughly $5–$15 for a batch of 100-500 profile scans depending on actor
- **Fit for MCC:** Works but adds operational complexity (external managed platform, webhook or polling for results). Less elegant than a direct ingestion script.
- **Verdict:** ⚠️ Viable but overkill for our volume

### PhantomBuster
- **URL:** https://phantombuster.com
- **LinkedIn phantoms:** "LinkedIn Profile Scraper", "LinkedIn Posts Extractor"
- **Pricing:** $56/mo (Starter) — includes scheduled runs
- **Fit for MCC:** Designed for non-technical users. Output is CSV/JSON via webhook. Would require a glue layer to import into MCC's DB.
- **Verdict:** ❌ Too much friction for our use case

### RapidAPI LinkedIn scrapers
- Various unofficial scrapers on RapidAPI marketplace (Fresh LinkedIn Profile Data, etc.)
- Reliability varies wildly — many go down without notice
- Pricing ~$10-50/mo for moderate usage
- **Verdict:** ❌ Avoid — too unreliable

---

## 4. Recommended Approach

### Ranking

| Approach | Cost | Reliability | Effort | Legal Risk | Verdict |
|---|---|---|---|---|---|
| `linkedin-api` (unofficial) | Free | Medium | Low | Medium | ✅ **#1 — Start here** |
| Proxycurl API | $30+/mo | High | Low | Low | ✅ **#2 — If budget exists** |
| Apify actors | $5-15/run | High | Medium | Low | ⚠️ Fallback |
| Official LinkedIn API | Free | High | Very High | None | ❌ Not viable |
| PhantomBuster | $56/mo | Medium | High | Low | ❌ Skip |

### Recommendation: `linkedin-api` first, Proxycurl if it breaks
Start with `linkedin-api` since it's already available, free, and has the right capabilities. Set up a dedicated LinkedIn account for the bot. If LinkedIn tightens anti-scraping or the library starts breaking frequently, migrate to Proxycurl (~$30/mo is cheap for the value).

### Data fields available vs. X

| Field | X (current) | LinkedIn (`linkedin-api`) |
|---|---|---|
| `external_id` | tweet ID | activity URN |
| `author` | @username | first/last name + profile URL |
| `content` | tweet text | post text (commentary) |
| `source_url` | x.com/user/status/... | linkedin.com/posts/... |
| `published_at` | created_at | createdAt timestamp |
| `likes` | like_count | socialDetail.totalSocialActivityCounts.numLikes |
| `retweets` | retweet_count | numShares |
| `replies` | reply_count | numComments |
| `links` | entities.urls | articles/links embedded in post |

### LinkedIn-specific concepts to model
- **Reactions** (not just likes): LIKE, CELEBRATE, SUPPORT, LOVE, INSIGHTFUL, FUNNY — we can store total as `likes` for simplicity
- **Reposts vs. original posts**: LinkedIn distinguishes `RESHARE` from original content — worth filtering to originals only or flagging reshares
- **Article links**: LinkedIn posts often link to LinkedIn Articles (separate content type) — worth extracting
- **URN format**: Post IDs are URNs like `urn:li:activity:1234567890` — use as `external_id`

---

## 5. Implementation Sketch

### Required env vars
```
LINKEDIN_EMAIL=bot@example.com
LINKEDIN_PASSWORD=...
LINKEDIN_PROFILE_IDS=austen-allred,gauntletai,some-other-id  # comma-separated public IDs
```

### `linkedin_ingestion.py` — skeleton

```python
#!/usr/bin/env python3
"""
LinkedIn Ingestion Pipeline
Fetches posts from configured LinkedIn profiles/companies.
Uses linkedin-api (unofficial Voyager API wrapper).
"""
import json, logging, os, time
from datetime import datetime
from typing import Optional

import psycopg2, psycopg2.extras
from dotenv import load_dotenv
from openai import OpenAI

# linkedin-api must be installed in the venv
from linkedin_api import Linkedin

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL = os.getenv('DATABASE_URL')
LI_EMAIL = os.getenv('LINKEDIN_EMAIL')
LI_PASSWORD = os.getenv('LINKEDIN_PASSWORD')
LI_PROFILE_IDS = [p.strip() for p in os.getenv('LINKEDIN_PROFILE_IDS', '').split(',') if p.strip()]
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
EMBEDDING_MODEL = 'text-embedding-3-small'
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1'
DEAD_LETTER_PATH = os.path.join(os.path.dirname(__file__), '../logs/dead_letter_linkedin.json')

log = logging.getLogger(__name__)


def get_post_text(post: dict) -> str:
    """Extract text content from a LinkedIn post object."""
    commentary = post.get('commentary', {})
    if isinstance(commentary, dict):
        return commentary.get('text', {}).get('text', '')
    return str(commentary) if commentary else ''


def parse_post(post: dict, author_id: str) -> Optional[dict]:
    """Normalize a LinkedIn post to MCC schema."""
    # Extract URN-based ID
    urn = post.get('entityUrn', post.get('dashEntityUrn', ''))
    activity_id = urn.split(':')[-1] if urn else None
    if not activity_id:
        return None

    content = get_post_text(post)
    if not content.strip():
        return None  # skip image-only, video-only posts

    social = post.get('socialDetail', {}).get('totalSocialActivityCounts', {})
    created_ms = post.get('created', {}).get('time', 0)
    created_at = datetime.utcfromtimestamp(created_ms / 1000) if created_ms else datetime.utcnow()

    # Extract links from content or article attachments
    links = []
    for content_item in post.get('content', {}).get('multiImage', {}).get('images', []):
        url = content_item.get('url', '')
        if url:
            links.append(url)
    # Also check article links
    article = post.get('content', {}).get('article', {})
    if article.get('source', {}).get('resolvedUrl'):
        links.append(article['source']['resolvedUrl'])

    source_url = f'https://www.linkedin.com/feed/update/{urn}/'

    return {
        'external_id': f'li_{activity_id}',
        'author': author_id,
        'content': content,
        'source_url': source_url,
        'published_at': created_at,
        'likes': social.get('numLikes', 0),
        'retweets': social.get('numShares', 0),
        'replies': social.get('numComments', 0),
        'links': json.dumps(links),
        'channel': 'linkedin_feed',
    }


def get_embeddings(client: OpenAI, texts: list) -> list:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def run():
    api = Linkedin(LI_EMAIL, LI_PASSWORD)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    openai_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=EMBEDDING_BASE_URL)

    all_posts = []

    for profile_id in LI_PROFILE_IDS:
        log.info(f'Fetching posts for {profile_id}')
        try:
            posts = api.get_profile_posts(public_id=profile_id, post_count=50)
            time.sleep(2)  # rate limiting — be polite
            for post in posts:
                parsed = parse_post(post, profile_id)
                if parsed:
                    # Check dedup
                    cur.execute('SELECT 1 FROM posts WHERE external_id = %s', (parsed['external_id'],))
                    if not cur.fetchone():
                        all_posts.append(parsed)
        except Exception as e:
            log.error(f'Failed to fetch posts for {profile_id}: {e}')
            continue

    if not all_posts:
        log.info('No new LinkedIn posts.')
        return

    # Embed in batches of 50
    BATCH = 50
    for i in range(0, len(all_posts), BATCH):
        batch = all_posts[i:i+BATCH]
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
                        published_at, likes, retweets, replies, channel, links, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_id) DO NOTHING
                ''', (
                    'linkedin', post['external_id'], post['author'], post['content'],
                    post['source_url'], post['published_at'],
                    post['likes'], post['retweets'], post['replies'],
                    post['channel'], post['links'], embedding
                ))
            except Exception as e:
                log.error(f'Insert failed for {post["external_id"]}: {e}')
                conn.rollback()

        conn.commit()
        log.info(f'Inserted batch {i//BATCH + 1} ({len(batch)} posts)')

    log.info(f'LinkedIn ingestion complete: {len(all_posts)} new posts')
    cur.close()
    conn.close()


if __name__ == '__main__':
    run()
```

### Plugging into MCC

1. Add `linkedin-api` to `backend/requirements.txt`
2. Add `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, `LINKEDIN_PROFILE_IDS` to `.env` and Railway env vars
3. Add `linkedin` checkpoint row to `ingestion_checkpoints` table
4. Add a daily cron job (same pattern as Slack/X ingestion crons)
5. Update the MCC frontend platform filter to include `linkedin`
6. Decide on the initial list of profiles to monitor: recommend starting with Gauntlet's company page + key team members + competitor companies

### Notes / Gotchas
- **Use a dedicated bot LinkedIn account** — not a personal account. LinkedIn's ToS violations can result in account suspension.
- **Cookies persist** — `linkedin-api` saves session cookies in `~/.cache/linkedin-api/`. These expire after ~1-2 weeks and require re-auth.
- **Post count limit**: `get_profile_posts(post_count=50)` is practical max per call without triggering throttling
- **Company pages**: use `api.get_company_updates(public_id='gauntletai')` instead of `get_profile_posts` for org pages
- **No `since_id` equivalent**: LinkedIn doesn't expose post IDs that sort chronologically like X snowflake IDs. Rely on deduplication via `external_id` in the DB.

---

## Usage Clarification (Updated 2026-04-14)

The primary use case for LinkedIn in MCC is **keyword/mention monitoring** — not profile following.

The @Mentions tab needs `api.search_posts(keywords="Gauntlet AI")` to get a broad pulse on what people are saying about Gauntlet AI across LinkedIn, regardless of who they are. This is the `linkedin_mentions_ingestion.py` path.

Profile-based ingestion (`get_profile_posts`) is a secondary feature (e.g., monitoring specific competitors or influencers) and can be built later if needed.

---

## Summary

| Question | Answer |
|---|---|
| Official API viable? | No — can't fetch arbitrary profiles |
| Best free option? | `linkedin-api` 2.3.1 (already installable) |
| Best paid option? | Proxycurl (~$30/mo) |
| Effort to implement? | ~1 day (ingestion script + env vars + cron) |
| Main risk? | LinkedIn ToS / account suspension — use a bot account |
| Data quality vs. X? | Comparable — text, engagement metrics, timestamps all available |
