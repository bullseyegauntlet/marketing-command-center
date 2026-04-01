#!/usr/bin/env python3
"""
Marketing Command Center — FastAPI Backend
"""
import asyncio
import json
import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional

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
        filters = []
        params = [req.query]
        sql = """
            SELECT id, platform, author, content, source_url, published_at,
                   likes, retweets, replies, channel,
                   ts_rank(content_tsv, plainto_tsquery('english', %s))::float as rank
            FROM posts
            WHERE content_tsv @@ plainto_tsquery('english', %s)
        """
        params.append(req.query)

        if req.platform:
            sql += " AND platform = %s"
            params.append(req.platform)
        if req.channel:
            sql += " AND channel = %s"
            params.append(req.channel)
        if req.days:
            sql += " AND published_at >= NOW() - INTERVAL '%s days'"
            params.append(req.days)

        # Blend relevance rank with recency: rank * 0.7 + recency_score * 0.3
        # recency_score decays over 90 days so recent posts rank higher when relevance is similar
        sql += """ ORDER BY (
            ts_rank(content_tsv, plainto_tsquery('english', %s))::float * 0.7
            + GREATEST(0, 1 - EXTRACT(EPOCH FROM (NOW() - published_at)) / 7776000.0) * 0.3
        ) DESC LIMIT %s"""
        params.append(req.query)  # second ts_rank ref in ORDER BY
        params.append(req.limit)

        cur.execute(sql, params)
        results = [dict(r) for r in cur.fetchall()]

        # Fallback: if full-text returns nothing, try ILIKE on individual words
        if not results:
            words = [w.strip() for w in req.query.split() if len(w.strip()) > 2]
            if words:
                like_conditions = ' OR '.join(['content ILIKE %s'] * len(words))
                fallback_sql = f"""
                    SELECT id, platform, author, content, source_url, published_at,
                           likes, retweets, replies, channel, 0.0 as rank
                    FROM posts
                    WHERE {like_conditions}
                """
                fallback_params = [f'%{w}%' for w in words]
                if req.platform:
                    fallback_sql += " AND platform = %s"
                    fallback_params.append(req.platform)
                if req.days:
                    fallback_sql += " AND published_at >= NOW() - INTERVAL '%s days'"
                    fallback_params.append(req.days)
                fallback_sql += " ORDER BY published_at DESC LIMIT %s"
                fallback_params.append(req.limit)
                cur.execute(fallback_sql, fallback_params)
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
    embedding = embed(req.query)
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

        if req.platform:
            sql += " AND platform = %s"
            params.append(req.platform)
        if req.channel:
            sql += " AND channel = %s"
            params.append(req.channel)
        if req.days:
            sql += " AND published_at >= NOW() - INTERVAL '%s days'"
            params.append(req.days)

        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
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
