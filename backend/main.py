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

def safe_json(obj):
    """JSON encoder that handles Decimal and other non-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
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

    # "last week / last month / last N days"
    m = re.search(r'\blast\s+(\d+)\s+days?\b', q)
    if m:
        days = int(m.group(1))
        date_from = f"NOW() - INTERVAL '{days} days'"
        query = re.sub(r'\blast\s+\d+\s+days?\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    m = re.search(r'\blast\s+week\b', q)
    if m:
        date_from = "NOW() - INTERVAL '7 days'"
        query = re.sub(r'\blast\s+week\b', '', query, flags=re.IGNORECASE).strip()
        return query.strip(), date_from, None

    m = re.search(r'\blast\s+month\b', q)
    if m:
        date_from = "NOW() - INTERVAL '30 days'"
        query = re.sub(r'\blast\s+month\b', '', query, flags=re.IGNORECASE).strip()
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

app = FastAPI(title='Marketing Command Center', version='1.0.0')
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

class KeywordQueryRequest(BaseModel):
    query: str
    platform: Optional[str] = None
    channel: Optional[str] = None
    limit: int = 20
    days: Optional[int] = None

class SemanticQueryRequest(BaseModel):
    query: str
    platform: Optional[str] = None
    channel: Optional[str] = None
    limit: int = 20
    days: Optional[int] = None

class CompareQueryRequest(BaseModel):
    query: str
    platform: Optional[str] = None
    channel: Optional[str] = None
    limit: int = 10
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
                'last_run_at': row['last_run_at'].isoformat() if row['last_run_at'] else None,
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
                'last_run_at': r['last_run_at'].isoformat() if r['last_run_at'] else None,
            }
            for r in cur.fetchall()
        ]
        return {
            'total_posts': total,
            'by_platform': by_platform,          # legacy key
            'posts_by_platform': by_platform,    # frontend expected key
            'project_updates': project_count,
            'queries_run': query_count,
            'last_ingestion': last_ingestion,
        }
    finally:
        cur.close()
        conn.close()


# ─── Keyword Query ─────────────────────────────────────────────────────────

@app.post('/api/query/keyword')
def keyword_query(req: KeywordQueryRequest):
    start = time.time()
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Parse temporal expressions from query text
        clean_query, date_from, date_to = parse_temporal(req.query)
        search_text = clean_query if clean_query else req.query

        params = [search_text]
        sql = """
            SELECT id, platform, author, content, source_url, published_at,
                   likes, retweets, replies, channel,
                   ts_rank(content_tsv, plainto_tsquery('english', %s))::float as rank
            FROM posts
            WHERE content_tsv @@ plainto_tsquery('english', %s)
        """
        params.append(search_text)

        # Apply temporal filters (from query text or explicit request params)
        if date_from and not date_from.startswith('NOW'):
            sql += " AND published_at >= %s"
            params.append(date_from)
        elif date_from:
            sql += f" AND published_at >= {date_from}"
        if date_to:
            sql += " AND published_at <= %s"
            params.append(date_to)
        if req.platform:
            sql += " AND platform = %s"
            params.append(req.platform)
        if req.channel:
            sql += " AND channel = %s"
            params.append(req.channel)
        if req.days and not date_from:
            sql += " AND published_at >= NOW() - INTERVAL '%s days'"
            params.append(req.days)

        # When time range is explicit: rank by relevance only
        # When no time filter: blend relevance 70% + recency 30%
        if date_from or date_to or req.days:
            sql += """ ORDER BY ts_rank(content_tsv, plainto_tsquery('english', %s))::float DESC LIMIT %s"""
            params.append(search_text)
        else:
            sql += """ ORDER BY (
                ts_rank(content_tsv, plainto_tsquery('english', %s))::float * 0.7
                + GREATEST(0, 1 - EXTRACT(EPOCH FROM (NOW() - published_at)) / 7776000.0) * 0.3
            ) DESC LIMIT %s"""
            params.append(search_text)
        params.append(req.limit)

        cur.execute(sql, params)
        results = [dict(r) for r in cur.fetchall()]

        # Fallback: if full-text returns nothing, try ILIKE on meaningful words only
        # Skip common English stopwords that match everything
        STOPWORDS = {'what','are','the','most','mentioned','about','with','this','that',
                     'from','have','been','will','were','they','them','their','there',
                     'when','where','which','who','how','why','all','any','some','more',
                     'very','just','also','into','over','than','then','these','those'}
        if not results:
            words = [w.strip() for w in search_text.split()
                     if len(w.strip()) > 3 and w.strip().lower() not in STOPWORDS]
            if words:
                like_conditions = ' OR '.join(['content ILIKE %s'] * len(words))
                fallback_sql = f"""
                    SELECT id, platform, author, content, source_url, published_at,
                           likes, retweets, replies, channel, 0.0 as rank
                    FROM posts
                    WHERE {like_conditions}
                """
                fallback_params = [f'%{w}%' for w in words]
                # Apply same temporal filters as main query
                if date_from and not date_from.startswith('NOW'):
                    fallback_sql += " AND published_at >= %s"
                    fallback_params.append(date_from)
                elif date_from:
                    fallback_sql += f" AND published_at >= {date_from}"
                if date_to:
                    fallback_sql += " AND published_at <= %s"
                    fallback_params.append(date_to)
                if req.platform:
                    fallback_sql += " AND platform = %s"
                    fallback_params.append(req.platform)
                if req.days and not date_from:
                    fallback_sql += " AND published_at >= NOW() - INTERVAL '%s days'"
                    fallback_params.append(req.days)
                fallback_sql += " ORDER BY published_at DESC LIMIT %s"
                fallback_params.append(req.limit)
                cur.execute(fallback_sql, fallback_params)
                results = [dict(r) for r in cur.fetchall()]

            # Last resort: if no meaningful words or ILIKE found nothing but we have a date range,
            # return most-engaged posts from that period
            if not results and (date_from or date_to):
                last_resort_sql = """
                    SELECT id, platform, author, content, source_url, published_at,
                           likes, retweets, replies, channel, 0.0 as rank
                    FROM posts WHERE 1=1
                """
                last_resort_params = []
                if date_from and not date_from.startswith('NOW'):
                    last_resort_sql += " AND published_at >= %s"
                    last_resort_params.append(date_from)
                elif date_from:
                    last_resort_sql += f" AND published_at >= {date_from}"
                if date_to:
                    last_resort_sql += " AND published_at <= %s"
                    last_resort_params.append(date_to)
                last_resort_sql += " ORDER BY (likes + retweets * 2) DESC, published_at DESC LIMIT %s"
                last_resort_params.append(req.limit)
                cur.execute(last_resort_sql, last_resort_params)
                results = [dict(r) for r in cur.fetchall()]

        for r in results:
            if r.get('published_at'):
                r['published_at'] = r['published_at'].isoformat()
            # Ensure all numeric fields are native Python types
            for k, v in r.items():
                if isinstance(v, Decimal):
                    r[k] = float(v)

        latency_ms = int((time.time() - start) * 1000)

        # Save to query_history
        cur.execute("""
            INSERT INTO query_history (user_id, query_text, filters, engine, results_snapshot, result_count, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ('system', req.query,
              json.dumps({'platform': req.platform, 'channel': req.channel, 'days': req.days}, default=safe_json),
              'keyword', json.dumps(results[:5], default=safe_json), len(results), latency_ms))
        conn.commit()

        return {'results': results, 'posts': results, 'count': len(results), 'latency_ms': latency_ms}
    finally:
        cur.close()
        conn.close()


# ─── Semantic Query ────────────────────────────────────────────────────────

@app.post('/api/query/semantic')
def semantic_query(req: SemanticQueryRequest):
    start = time.time()
    # Parse temporal expressions before embedding (embed the clean query)
    clean_query, date_from, date_to = parse_temporal(req.query)
    search_text = clean_query if clean_query else req.query
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
        if req.platform:
            sql += " AND platform = %s"
            params.append(req.platform)
        if req.channel:
            sql += " AND channel = %s"
            params.append(req.channel)
        if req.days and not date_from:
            sql += " AND published_at >= NOW() - INTERVAL '%s days'"
            params.append(req.days)

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
                r['published_at'] = r['published_at'].isoformat()
            for k, v in r.items():
                if isinstance(v, Decimal):
                    r[k] = float(v)

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


# ─── Compare Query ─────────────────────────────────────────────────────────

@app.post('/api/query/compare')
def compare_query(req: CompareQueryRequest):
    start = time.time()

    # Run both in parallel via threads
    keyword_req = KeywordQueryRequest(query=req.query, platform=req.platform,
                                       channel=req.channel, limit=req.limit, days=req.days)
    semantic_req = SemanticQueryRequest(query=req.query, platform=req.platform,
                                         channel=req.channel, limit=req.limit, days=req.days)

    kw_results = keyword_query(keyword_req)
    sem_results = semantic_query(semantic_req)

    # Generate grounded summary via Claude
    combined = kw_results['results'][:5] + sem_results['results'][:5]
    snippets = '\n'.join([f"- {r['author']}: {r['content'][:200]}" for r in combined])
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
              'side_by_side', summary,
              json.dumps({'keyword': kw_results['results'][:3], 'semantic': sem_results['results'][:3]}, default=safe_json),
              kw_results['count'] + sem_results['count'], latency_ms))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return {
        'keyword': kw_results,
        'semantic': sem_results,
        'summary': summary,
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
                r['created_at'] = r['created_at'].isoformat()
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
            r['created_at'] = r['created_at'].isoformat()
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
                r['published_at'] = r['published_at'].isoformat()
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
                r['published_at'] = r['published_at'].isoformat()
        return {'project': name, 'history': rows}
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
