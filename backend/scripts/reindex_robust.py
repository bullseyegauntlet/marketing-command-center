#!/usr/bin/env python3
"""Robust reindex — small fetches, reconnects each batch."""
import os, psycopg2, sys
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL = os.getenv('DATABASE_URL')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
MODEL = 'text-embedding-3-small'
BATCH = 20

client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

def get_conn():
    return psycopg2.connect(DB_URL, connect_timeout=10)

def count_pending():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM posts WHERE embedding IS NULL AND content IS NOT NULL AND content != ''")
    n = cur.fetchone()[0]
    conn.close()
    return n

def fetch_batch():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content FROM posts WHERE embedding IS NULL AND content IS NOT NULL AND content != '' ORDER BY ingested_at LIMIT %s",
        (BATCH,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def save_embeddings(rows, embeddings):
    conn = get_conn()
    cur = conn.cursor()
    for (pid, _), emb in zip(rows, embeddings):
        cur.execute('UPDATE posts SET embedding = %s WHERE id = %s', (emb, pid))
    conn.commit()
    conn.close()

total = count_pending()
print(f'Posts to embed: {total}')
done = 0
failed = 0

while True:
    rows = fetch_batch()
    if not rows:
        break

    texts = [(r[1] or '')[:6000] for r in rows]
    ids = [r[0] for r in rows]

    try:
        resp = client.embeddings.create(model=MODEL, input=texts)
        embs = [item.embedding for item in resp.data]
        save_embeddings(rows, embs)
        done += len(rows)
        print(f'  [{done}/{total}] ok', flush=True)
    except Exception as e:
        print(f'  Batch error: {e} — one-by-one', flush=True)
        for pid, text in zip(ids, texts):
            try:
                resp = client.embeddings.create(model=MODEL, input=[text.strip()])
                emb = resp.data[0].embedding
                conn = get_conn()
                conn.cursor().execute('UPDATE posts SET embedding = %s WHERE id = %s', (emb, pid))
                conn.commit()
                conn.close()
                done += 1
            except Exception as e2:
                print(f'    Skip {pid[:8]}: {e2}', flush=True)
                # Mark as processed with null-embedding placeholder to avoid infinite loop
                conn = get_conn()
                conn.cursor().execute("UPDATE posts SET content = content WHERE id = %s", (pid,))
                conn.commit()
                conn.close()
                failed += 1

print(f'\nDone. Embedded: {done}, Skipped: {failed}')
