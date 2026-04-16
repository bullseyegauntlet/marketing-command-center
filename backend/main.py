#!/usr/bin/env python3
"""
Marketing Command Center — FastAPI Backend
"""
import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

import psycopg2
import psycopg2.extras
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI, RateLimitError as OpenAIRateLimitError
from pydantic import BaseModel

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))

# ─── Slack User Map ────────────────────────────────────────────────────────
_slack_users: dict = {}
_slack_users_path = os.path.join(os.path.dirname(__file__), 'slack_users.json')
if os.path.exists(_slack_users_path):
    with open(_slack_users_path) as _f:
        _slack_users = json.load(_f)

def resolve_slack_author(author: str) -> str:
    """Resolve a Slack user ID (e.g. U086X3AQH5M) to a display name."""
    if author and author.startswith('U') and len(author) > 8:
        return _slack_users.get(author, author)
    return author

def safe_json(obj):
    """JSON encoder that handles Decimal and other non-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat() + 'Z'
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

MONTHS = {
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
    'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,
    'sep':9,'sept':9,'oct':10,'nov':11,'dec':12,
}


def parse_temporal(query: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Extract temporal expressions from a query string.
    Returns: (cleaned_query, date_from, date_to)
    date_from/date_to are ISO date strings or None.
    """
    q = query.lower().strip()
    date_from = None
    date_to = None
    original = query

    # "in [month] [year]" or "in [month], [year]"
    m = re.search(r'\bin\s+(' + '|'.join(MONTHS.keys()) + r')[,\s]+(\d{4})\b', q)
    if m:
        month = MONTHS[m.group(1)]
        year = int(m.group(2))
        import calendar
        _, last_day = calendar.monthrange(year, month)
        date_from = f"{year}-{month:02d}-01"
        date_to = f"{year}-{month:02d}-{last_day:02d}"
        query = re.sub(r'\bin\s+(' + '|'.join(MONTHS.keys()) + r')[,\s]+\d{4}\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, date_to

    # "[month] [year]" anywhere
    m = re.search(r'\b(' + '|'.join(MONTHS.keys()) + r')\s+(\d{4})\b', q)
    if m:
        month = MONTHS[m.group(1)]
        year = int(m.group(2))
        import calendar
        _, last_day = calendar.monthrange(year, month)
        date_from = f"{year}-{month:02d}-01"
        date_to = f"{year}-{month:02d}-{last_day:02d}"
        query = re.sub(r'\b(' + '|'.join(MONTHS.keys()) + r')\s+\d{4}\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, date_to

    # "in [year]" e.g. "in 2025"
    m = re.search(r'\bin\s+(20\d{2})\b', q)
    if m:
        year = int(m.group(1))
        date_from = f"{year}-01-01"
        date_to = f"{year}-12-31"
        query = re.sub(r'\bin\s+20\d{2}\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, date_to

    # Relative time expressions — all stored as "NOW() - INTERVAL '...'" strings
    # "today" / "this week" / "this month" / "yesterday"
    for pattern, interval in [
        (r'\byesterday\b', "NOW() - INTERVAL '2 days'"),
        (r'\btoday\b', "NOW() - INTERVAL '1 day'"),
        (r'\bthis\s+week\b', "NOW() - INTERVAL '7 days'"),
        (r'\bthis\s+month\b', "NOW() - INTERVAL '30 days'"),
        (r'\bthis\s+year\b', "NOW() - INTERVAL '365 days'"),
    ]:
        m = re.search(pattern, q)
        if m:
            date_from = interval
            query = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
            return query.strip(), date_from, None

    # "last N weeks" / "past N weeks"
    m = re.search(r'\b(?:last|past)\s+(\d+)\s+weeks?\b', q)
    if m:
        weeks = int(m.group(1))
        date_from = f"NOW() - INTERVAL '{weeks * 7} days'"
        query = re.sub(r'\b(?:last|past)\s+\d+\s+weeks?\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "last N months" / "past N months"
    m = re.search(r'\b(?:last|past)\s+(\d+)\s+months?\b', q)
    if m:
        months = int(m.group(1))
        date_from = f"NOW() - INTERVAL '{months * 30} days'"
        query = re.sub(r'\b(?:last|past)\s+\d+\s+months?\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "last N days" / "past N days"
    m = re.search(r'\b(?:last|past)\s+(\d+)\s+days?\b', q)
    if m:
        days = int(m.group(1))
        date_from = f"NOW() - INTERVAL '{days} days'"
        query = re.sub(r'\b(?:last|past)\s+\d+\s+days?\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "last week" / "past week"
    m = re.search(r'\b(?:last|past)\s+week\b', q)
    if m:
        date_from = "NOW() - INTERVAL '7 days'"
        query = re.sub(r'\b(?:last|past)\s+week\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "last month" / "past month"
    m = re.search(r'\b(?:last|past)\s+month\b', q)
    if m:
        date_from = "NOW() - INTERVAL '30 days'"
        query = re.sub(r'\b(?:last|past)\s+month\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "since [month]" — relative month, current year assumed (or last year if month is in future)
    m = re.search(r'\bsince\s+(' + '|'.join(MONTHS.keys()) + r')\b', q)
    if m:
        import calendar as _cal
        from datetime import date as _date
        month_name = m.group(1)
        month_num = MONTHS[month_name]
        today = _date.today()
        # If the named month is in the future this year, use last year
        year = today.year if month_num <= today.month else today.year - 1
        date_from = f"{year}-{month_num:02d}-01"
        query = re.sub(r'\bsince\s+(' + '|'.join(MONTHS.keys()) + r')\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "since [month] [year]"
    m = re.search(r'\bsince\s+(' + '|'.join(MONTHS.keys()) + r')\s+(\d{4})\b', q)
    if m:
        month_num = MONTHS[m.group(1)]
        year = int(m.group(2))
        date_from = f"{year}-{month_num:02d}-01"
        query = re.sub(r'\bsince\s+(' + '|'.join(MONTHS.keys()) + r')\s+\d{4}\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # "recently" / "recent" — treat as last 14 days
    m = re.search(r'\brecentl?y?\b', q)
    if m:
        date_from = "NOW() - INTERVAL '14 days'"
        query = re.sub(r'\brecentl?y?\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    # Q1/Q2/Q3/Q4 [year]
    m = re.search(r'\bq([1-4])\s+(20\d{2})\b', q)
    if m:
        quarter = int(m.group(1))
        year = int(m.group(2))
        month_start = (quarter - 1) * 3 + 1
        month_end = quarter * 3
        import calendar
        _, last_day = calendar.monthrange(year, month_end)
        date_from = f"{year}-{month_start:02d}-01"
        date_to = f"{year}-{month_end:02d}-{last_day:02d}"
        query = re.sub(r'\bq[1-4]\s+20\d{2}\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, date_to

    return query.strip(), None, None

DB_URL = os.getenv('DATABASE_URL')
# Support OpenRouter (preferred) or OpenAI directly
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
SUMMARY_MODEL = 'anthropic/claude-sonnet-4-5'
EMBEDDING_MODEL = 'text-embedding-3-small'

ALLOWED_ORIGINS = [
    'https://marketing-command-center-55ff2635.netlify.app',
    'http://localhost:3000',
    'http://localhost:3001',
]

app = FastAPI(
    title='Marketing Command Center',
    version='1.0.0',
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure CORS headers are present even on unhandled 500 errors."""
    origin = request.headers.get('origin', '')
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers['Access-Control-Allow-Origin'] = origin
        headers['Access-Control-Allow-Credentials'] = 'true'
    return JSONResponse(
        status_code=500,
        content={'detail': str(exc)},
        headers=headers,
    )


openai_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL) if EMBEDDING_API_KEY else None
# Summary client — uses OpenRouter (OpenAI-compatible) so no separate Anthropic SDK needed
summary_client = OpenAI(api_key=EMBEDDING_API_KEY, base_url='https://openrouter.ai/api/v1') if EMBEDDING_API_KEY else None


def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def embed(text: str) -> list:
    if not openai_client:
        raise HTTPException(status_code=503, detail='OpenAI client not configured')
    try:
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
        return response.data[0].embedding
    except OpenAIRateLimitError as e:
        raise HTTPException(status_code=503, detail=f'OpenAI quota exceeded — semantic search unavailable: {e}')


# ─── Request/Response Models ───────────────────────────────────────────────

class SemanticQueryRequest(BaseModel):
    query: str
    platform: Optional[str] = None
    channel: Optional[str] = None
    limit: int = 100          # fetch pool; relevance filter applied post-query
    min_score: float = 0.3    # drop results below this similarity threshold
    days: Optional[int] = None

class CompareQueryRequest(BaseModel):
    query: str
    platform: Optional[str] = None
    channel: Optional[str] = None
    limit: int = 100
    min_score: float = 0.3
    days: Optional[int] = None


# ─── Health ────────────────────────────────────────────────────────────────

@app.get('/api/health')
def health():
    conn = get_conn()
    cur = conn.cursor()
    status = {'db': 'ok', 'pipelines': {}}
    try:
        cur.execute("SELECT source, status, last_run_at, consecutive_failures FROM ingestion_checkpoints")
        for row in cur.fetchall():
            status['pipelines'][row['source']] = {
                'status': row['status'],
                'last_run_at': row['last_run_at'].isoformat() + 'Z' if row['last_run_at'] else None,
                'consecutive_failures': row['consecutive_failures'],
            }
        cur.execute("SELECT COUNT(*) as total FROM posts")
        status['post_count'] = cur.fetchone()['total']
    except Exception as e:
        status['db'] = f'error: {e}'
    finally:
        cur.close()
        conn.close()
    return status


# ─── Stats ─────────────────────────────────────────────────────────────────

@app.get('/api/stats')
def stats():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as total FROM posts")
        total = cur.fetchone()['total']
        cur.execute("SELECT platform, COUNT(*) as cnt FROM posts GROUP BY platform")
        by_platform = {r['platform']: r['cnt'] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as total FROM project_updates")
        project_count = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM query_history")
        query_count = cur.fetchone()['total']
        # Also pull ingestion checkpoint data for last_ingestion field
        cur.execute("SELECT source, status, last_run_at FROM ingestion_checkpoints")
        last_ingestion = [
            {
                'source': r['source'],
                'status': r['status'],
                'last_run_at': r['last_run_at'].isoformat() + 'Z' if r['last_run_at'] else None,
            }
            for r in cur.fetchall()
        ]
        # Mention stats
        mention_total = 0
        mention_last_24h = 0
        mention_by_platform: dict = {}
        try:
            cur.execute("SELECT COUNT(*) as total FROM posts WHERE is_mention = TRUE")
            mention_total = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as cnt FROM posts WHERE is_mention = TRUE AND published_at >= NOW() - INTERVAL '24 hours'")
            mention_last_24h = cur.fetchone()['cnt']
            cur.execute("SELECT platform, COUNT(*) as cnt FROM posts WHERE is_mention = TRUE GROUP BY platform")
            mention_by_platform = {r['platform']: r['cnt'] for r in cur.fetchall()}
        except Exception:
            pass

        

        # Popular posts stats
        popular_total = 0
        popular_last_24h = 0
        try:
            cur.execute("SELECT COUNT(*) as total FROM popular_posts")
            popular_total = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as cnt FROM popular_posts WHERE flagged_at >= NOW() - INTERVAL '24 hours'")
            popular_last_24h = cur.fetchone()['cnt']
        except Exception:
            pass  # table may not exist yet before migration runs

        return {
            'total_posts': total,
            'by_platform': by_platform,          # legacy key
            'posts_by_platform': by_platform,    # frontend expected key
            'project_updates': project_count,
            'queries_run': query_count,
            'last_ingestion': last_ingestion,
            'mentions': {
                'total': mention_total,
                'last_24h': mention_last_24h,
                'x': mention_by_platform.get('x', 0),
                'linkedin': mention_by_platform.get('linkedin', 0),
                'reddit': mention_by_platform.get('reddit', 0),
            },
            'popular': {
                'total': popular_total,
                'last_24h': popular_last_24h,
            },
        }
    finally:
        cur.close()
        conn.close()


# ─── Semantic Query ────────────────────────────────────────────────────────

def _parse_platform(query: str) -> Tuple[str, Optional[str]]:
    """Detect platform filter from query text (x/slack)."""
    q = query
    platform = None
    patterns_slack = [
        r'\b(?:on|from|in|about)\s+slack\b',
        r'\bslack\s+(?:posts?|messages?|content|discussions?|conversations?)\b',
        r'\bslack\s+only\b',
        r'\bfrom\s+the\s+slack\b',
        r'\bslack\s+channel\b',
    ]
    patterns_x = [
        r'\b(?:on|from|in)\s+(?:x|twitter)\b',
        r'\b(?:x|twitter)\s+(?:posts?|tweets?|content|opinions?|discussions?|thoughts?)\b',
        r'\b(?:x|twitter)\s+only\b',
        r'\bfrom\s+(?:x|twitter)\b',
        r'\btwitter\b',
    ]
    for pat in patterns_slack:
        if re.search(pat, q, re.IGNORECASE):
            platform = 'slack'
            q = re.sub(pat, '', q, flags=re.IGNORECASE).strip()
            break
    if not platform:
        for pat in patterns_x:
            if re.search(pat, q, re.IGNORECASE):
                platform = 'x'
                q = re.sub(pat, '', q, flags=re.IGNORECASE).strip()
                break
    q = re.sub(r'\s{2,}', ' ', q).strip().strip(',').strip()
    return q, platform


@app.post('/api/query/semantic')
def semantic_query(req: SemanticQueryRequest):
    start = time.time()
    # Parse temporal expressions before embedding (embed the clean query)
    query_after_platform, detected_platform = _parse_platform(req.query)
    effective_platform = detected_platform or req.platform
    clean_query, date_from, date_to = parse_temporal(query_after_platform)
    search_text = clean_query if clean_query else query_after_platform
    embedding = embed(search_text)
    conn = get_conn()
    cur = conn.cursor()
    try:
        sql = """
            SELECT id, platform, author, content, source_url, published_at,
                   likes, retweets, replies, channel,
                   1 - (embedding <=> %s::vector) as similarity
            FROM posts
            WHERE embedding IS NOT NULL
              AND platform IN ('x', 'slack')
        """
        params = [embedding]

        # Apply temporal filters
        if date_from and not date_from.startswith('NOW'):
            sql += " AND published_at >= %s"
            params.append(date_from)
        elif date_from:
            sql += f" AND published_at >= {date_from}"
        if date_to:
            sql += " AND published_at <= %s"
            params.append(date_to)
        if effective_platform:
            sql += " AND platform = %s"
            params.append(effective_platform)
        if req.channel:
            sql += " AND channel = %s"
            params.append(req.channel)
        if req.days and not date_from:
            sql += f" AND published_at >= NOW() - INTERVAL '{int(req.days)} days'"

        # When time range explicit: rank by similarity only; otherwise blend with recency
        if date_from or date_to or req.days:
            sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        else:
            sql += """ ORDER BY (
                (1 - (embedding <=> %s::vector)) * 0.7
                + GREATEST(0, 1 - EXTRACT(EPOCH FROM (NOW() - published_at)) / 7776000.0) * 0.3
            ) DESC LIMIT %s"""
        params.extend([embedding, req.limit])

        cur.execute(sql, params)
        results = [dict(r) for r in cur.fetchall()]
        for r in results:
            if r.get('published_at'):
                r['published_at'] = r['published_at'].isoformat() + 'Z'
            for k, v in r.items():
                if isinstance(v, Decimal):
                    r[k] = float(v)
            if r.get('platform') == 'slack':
                r['author'] = resolve_slack_author(r.get('author', ''))
        # Filter to relevant results only
        results = [r for r in results if float(r.get('similarity', 0)) >= req.min_score]

        latency_ms = int((time.time() - start) * 1000)

        cur.execute("""
            INSERT INTO query_history (user_id, query_text, filters, engine, results_snapshot, result_count, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ('system', req.query,
              json.dumps({'platform': req.platform, 'channel': req.channel, 'days': req.days}, default=safe_json),
              'semantic', json.dumps(results[:5], default=safe_json), len(results), latency_ms))
        conn.commit()

        return {'results': results, 'posts': results, 'count': len(results), 'latency_ms': latency_ms}
    finally:
        cur.close()
        conn.close()


# ─── Semantic with Summary ─────────────────────────────────────────────────

@app.post('/api/query/semantic-with-summary')
def semantic_with_summary(req: CompareQueryRequest):
    start = time.time()

    sem_req = SemanticQueryRequest(query=req.query, platform=req.platform,
                                   channel=req.channel, limit=req.limit, days=req.days)
    sem_results = semantic_query(sem_req)

    # Generate grounded summary via Claude
    snippets = '\n'.join([f"- {r['author']}: {r['content'][:200]}" for r in sem_results['results'][:10]])
    summary = ''
    try:
        if not summary_client:
            raise ValueError('Summary client not configured')
        msg = summary_client.chat.completions.create(
            model=SUMMARY_MODEL,
            max_tokens=512,
            messages=[{
                'role': 'user',
                'content': f'Query: "{req.query}"\n\nRelevant posts:\n{snippets}\n\nWrite a 2-3 sentence grounded summary of what these posts say about the query. Cite specific people or sources.'
            }]
        )
        summary = msg.choices[0].message.content
    except Exception as e:
        summary = f'(summary unavailable: {e})'

    latency_ms = int((time.time() - start) * 1000)

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO query_history (user_id, query_text, filters, engine, summary, results_snapshot, result_count, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, ('system', req.query,
              json.dumps({'platform': req.platform, 'channel': req.channel, 'days': req.days}, default=safe_json),
              'semantic_with_summary', summary,
              json.dumps(sem_results['results'][:5], default=safe_json),
              sem_results['count'], latency_ms))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return {
        'results': sem_results['results'],
        'posts': sem_results['results'],
        'summary': summary,
        'count': sem_results['count'],
        'latency_ms': latency_ms,
    }


# ─── Query History ─────────────────────────────────────────────────────────

@app.get('/api/query/history')
def query_history(
    limit: int = Query(20),
    offset: int = Query(0),
    page: int = Query(1),
    page_size: int = Query(20),
):
    # Support both limit/offset and page/page_size
    effective_limit = limit if limit != 20 else page_size
    effective_offset = offset if offset != 0 else (page - 1) * page_size
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, query_text, engine, result_count, latency_ms, created_at
            FROM query_history ORDER BY created_at DESC LIMIT %s OFFSET %s
        """, (effective_limit, effective_offset))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat() + 'Z'
        cur.execute("SELECT COUNT(*) as total FROM query_history")
        total = cur.fetchone()['total']
        return {
            'items': rows,       # frontend expected key
            'results': rows,     # legacy key
            'total': total,
            'page': page,
            'page_size': effective_limit,
        }
    finally:
        cur.close()
        conn.close()


@app.get('/api/query/history/{query_id}')
def query_history_detail(query_id: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM query_history WHERE id = %s", (query_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Query not found')
        r = dict(row)
        if r.get('created_at'):
            r['created_at'] = r['created_at'].isoformat() + 'Z'
        # Resolve Slack user IDs in snapshot
        if r.get('results_snapshot'):
            snapshot = r['results_snapshot'] if isinstance(r['results_snapshot'], list) else []
            for res in snapshot:
                if isinstance(res, dict) and res.get('platform') == 'slack':
                    res['author'] = resolve_slack_author(res.get('author', ''))
            r['results_snapshot'] = snapshot
        return r
    finally:
        cur.close()
        conn.close()


@app.get('/api/query/history/{query_id}/export')
def query_history_export(query_id: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM query_history WHERE id = %s", (query_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Query not found')
        r = dict(row)
        md = f"# Query Export\n\n**Query:** {r['query_text']}\n**Engine:** {r['engine']}\n**Results:** {r['result_count']}\n\n"
        if r.get('summary'):
            md += f"## Summary\n{r['summary']}\n\n"
        if r.get('results_snapshot'):
            md += "## Results\n"
            results = r['results_snapshot'] if isinstance(r['results_snapshot'], list) else []
            for res in results[:10]:
                md += f"- **{res.get('author', 'unknown')}**: {res.get('content', '')[:200]}\n  [{res.get('source_url', '')}]\n\n"
        return {'markdown': md, 'query_id': query_id}
    finally:
        cur.close()
        conn.close()


# ─── Mentions ──────────────────────────────────────────────────────────────

@app.get('/api/mentions')
def mentions(
    platform: Optional[str] = Query(None, description="x | linkedin | all"),
    days: int = Query(7, description="Look-back window in days"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_conn()
    cur = conn.cursor()
    try:
        where_clauses = [
            "p.is_mention = TRUE",
            "p.published_at >= NOW() - INTERVAL '1 day' * %s",
        ]
        params: list = [days]

        if platform and platform != 'all':
            where_clauses.append("p.platform = %s")
            params.append(platform)

        where_sql = " AND ".join(where_clauses)
        offset = (page - 1) * page_size

        cur.execute(f"SELECT COUNT(*) as total FROM posts p WHERE {where_sql}", params)
        total = cur.fetchone()['total']

        cur.execute(f"""
            SELECT p.platform, COUNT(*) as cnt
            FROM posts p WHERE {where_sql}
            GROUP BY p.platform
        """, params)
        by_platform = {r['platform']: r['cnt'] for r in cur.fetchall()}

        cur.execute(f"""
            SELECT id, platform, external_id, author, content, source_url,
                   published_at, ingested_at, likes, retweets, replies, views, channel
            FROM posts p
            WHERE {where_sql}
            ORDER BY published_at DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])

        rows = []
        for r in cur.fetchall():
            row = dict(r)
            if row.get('published_at'):
                row['published_at'] = row['published_at'].isoformat() + 'Z'
            if row.get('ingested_at'):
                row['ingested_at'] = row['ingested_at'].isoformat() + 'Z'
            if row.get('platform') == 'slack':
                row['author'] = resolve_slack_author(row.get('author', ''))
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
            rows.append(row)

        return {
            'mentions': rows,
            'posts': rows,  # alias for ResultCard compatibility
            'total': total,
            'page': page,
            'page_size': page_size,
            'by_platform': {
                'x': by_platform.get('x', 0),
                'reddit': by_platform.get('reddit', 0),
                'linkedin': by_platform.get('linkedin', 0),
            },
        }
    finally:
        cur.close()
        conn.close()


# ─── Popular Posts ─────────────────────────────────────────────────────────

@app.get('/api/popular')
def popular_posts(
    platform: Optional[str] = Query(None, description="x | slack | all"),
    days: int = Query(30, description="Look-back window in days (based on flagged_at)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_conn()
    cur = conn.cursor()
    try:
        where_clauses = ["pp.flagged_at >= NOW() - INTERVAL '1 day' * %s"]
        params: list = [days]

        if platform and platform != 'all':
            where_clauses.append("p.platform = %s")
            params.append(platform)

        where_sql = " AND ".join(where_clauses)
        offset = (page - 1) * page_size

        # Total count
        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM popular_posts pp
            JOIN posts p ON p.id = pp.post_id
            WHERE {where_sql}
        """, params)
        total = cur.fetchone()['total']

        # By-platform breakdown
        cur.execute(f"""
            SELECT p.platform, COUNT(*) as cnt
            FROM popular_posts pp
            JOIN posts p ON p.id = pp.post_id
            WHERE {where_sql}
            GROUP BY p.platform
        """, params)
        by_platform = {r['platform']: r['cnt'] for r in cur.fetchall()}

        # Paginated results
        cur.execute(f"""
            SELECT
                p.id, p.platform, p.external_id, p.author, p.content,
                p.source_url, p.published_at, p.ingested_at,
                p.likes, p.retweets, p.replies, p.views, p.channel,
                pp.flagged_at, pp.triggered_by, pp.metric_value
            FROM popular_posts pp
            JOIN posts p ON p.id = pp.post_id
            WHERE {where_sql}
            ORDER BY pp.flagged_at DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])

        rows = []
        for r in cur.fetchall():
            row = dict(r)
            if row.get('published_at'):
                row['published_at'] = row['published_at'].isoformat() + 'Z'
            if row.get('ingested_at'):
                row['ingested_at'] = row['ingested_at'].isoformat() + 'Z'
            if row.get('flagged_at'):
                row['flagged_at'] = row['flagged_at'].isoformat() + 'Z'
            if row.get('platform') == 'slack':
                row['author'] = resolve_slack_author(row.get('author', ''))
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
            rows.append(row)

        return {
            'posts': rows,
            'total': total,
            'page': page,
            'page_size': page_size,
            'by_platform': {'x': by_platform.get('x', 0), 'slack': by_platform.get('slack', 0)},
        }
    finally:
        cur.close()
        conn.close()


# ─── Projects ──────────────────────────────────────────────────────────────

@app.get('/api/projects')
def projects():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT ON (project_name) project_name, status, update_text, published_at
            FROM project_updates ORDER BY project_name, published_at DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get('published_at'):
                r['published_at'] = r['published_at'].isoformat() + 'Z'
        return {'projects': rows}
    finally:
        cur.close()
        conn.close()


@app.get('/api/projects/{name}/history')
def project_history(name: str, limit: int = Query(20)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT * FROM project_updates WHERE project_name = %s
            ORDER BY published_at DESC LIMIT %s
        """, (name, limit))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get('published_at'):
                r['published_at'] = r['published_at'].isoformat() + 'Z'
        return {'project': name, 'history': rows}
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
