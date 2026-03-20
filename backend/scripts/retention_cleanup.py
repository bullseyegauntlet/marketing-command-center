#!/usr/bin/env python3
"""
Data retention cleanup: deletes posts and query_history older than 1 year.
Run weekly via cron.

Usage:
    python retention_cleanup.py
"""
import os
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

DB_URL = os.getenv('DATABASE_URL')
RETENTION_DAYS = 365


def main():
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    print(f'[{datetime.utcnow().isoformat()}] Running retention cleanup. Cutoff: {cutoff.date()}')

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute('DELETE FROM posts WHERE ingested_at < %s', (cutoff,))
    posts_deleted = cur.rowcount

    cur.execute('DELETE FROM query_history WHERE created_at < %s', (cutoff,))
    queries_deleted = cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    print(f'Deleted {posts_deleted} posts older than {RETENTION_DAYS} days')
    print(f'Deleted {queries_deleted} query_history records older than {RETENTION_DAYS} days')
    print('Retention cleanup complete.')


if __name__ == '__main__':
    main()
