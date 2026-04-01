#!/usr/bin/env python3
"""
Re-index embeddings for all posts in the database.
Use this when switching embedding models.

Usage:
    python reindex_embeddings.py [--dry-run] [--batch-size 100]
"""
import argparse
import os
import sys
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL = os.getenv('DATABASE_URL')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
EMBEDDING_BASE_URL = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else None
EMBEDDING_MODEL = 'text-embedding-3-small'
EMBEDDING_DIM = 1536


def get_embeddings(client, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def main():
    parser = argparse.ArgumentParser(description='Re-index post embeddings')
    parser.add_argument('--dry-run', action='store_true', help='Report count without embedding')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for API calls')
    args = parser.parse_args()

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM posts')
    total = cur.fetchone()[0]
    print(f'Total posts: {total}')

    if args.dry_run:
        print(f'[dry-run] Would re-embed {total} posts in batches of {args.batch_size}')
        cur.close()
        conn.close()
        return

    client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    cur.execute('SELECT id, content FROM posts ORDER BY ingested_at')
    rows = cur.fetchall()

    # Only process posts that don't have embeddings yet
    cur.execute('SELECT id, content FROM posts WHERE embedding IS NULL ORDER BY ingested_at')
    rows = cur.fetchall()
    total_pending = len(rows)
    print(f'Posts needing embeddings: {total_pending}')

    updated = 0
    for i in range(0, len(rows), args.batch_size):
        batch = rows[i:i + args.batch_size]
        ids = [r[0] for r in batch]
        texts = [str(r[1] or '')[:8000] for r in batch]  # truncate to avoid token limits

        print(f'Embedding batch {i // args.batch_size + 1} ({len(batch)} posts)...')
        try:
            embeddings = get_embeddings(client, texts)
        except Exception as e:
            print(f'  Batch failed: {e} — skipping and continuing')
            # Try one at a time to salvage the rest
            embeddings = []
            for tid, text in zip(ids, texts):
                try:
                    emb = get_embeddings(client, [text])
                    embeddings.append(emb[0])
                except Exception:
                    embeddings.append(None)

        for post_id, embedding in zip(ids, embeddings):
            if embedding is None:
                continue
            cur.execute(
                'UPDATE posts SET embedding = %s WHERE id = %s',
                (embedding, post_id)
            )
        conn.commit()
        updated += len(batch)
        print(f'  Updated {updated}/{total_pending}')

    print(f'Done. Re-indexed {updated} posts.')
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
