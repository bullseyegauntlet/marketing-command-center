#!/usr/bin/env python3
"""
OpenClaw Project Update Listener
Called from slack_ingestion.py after inserting Slack messages.
Detects OpenClaw project update messages and inserts into project_updates table.
"""
import logging
import re
from datetime import datetime

log = logging.getLogger(__name__)

# Status keywords mapped to enum values
STATUS_PATTERNS = {
    'on_track': [r'\bon.?track\b', r'\bgreen\b', r'\bon schedule\b'],
    'at_risk':  [r'\bat.?risk\b', r'\byellow\b', r'\bconcern\b'],
    'blocked':  [r'\bblocked\b', r'\bstuck\b', r'\bblocker\b', r'\bred\b'],
    'completed': [r'\bcomplete[d]?\b', r'\bdone\b', r'\bshipped\b', r'\blaunched\b'],
}

# Bullseye bot user IDs (add more if needed)
OPENCLAW_USER_IDS = {'U0AJ82DSX24'}  # bullseye bot user ID


def detect_status(text: str) -> str | None:
    text_lower = text.lower()
    for status, patterns in STATUS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return status
    return None


def extract_project_name(text: str) -> str | None:
    """Try to extract a project name from the update text."""
    # Look for "Project: X" or "**X**" at start of message
    patterns = [
        r'(?:project|proj)[:\s]+([^\n]+)',
        r'^\*\*([^*]+)\*\*',
        r'^#+\s*([^\n]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()[:100]
    # Fall back to first line if short enough
    first_line = text.split('\n')[0].strip()
    if 10 < len(first_line) < 80:
        return first_line
    return 'General Update'


def process_message(cur, conn, message: dict, channel_id: str):
    """
    Check if a Slack message is an OpenClaw project update.
    If so, insert into project_updates table.
    This is best-effort — exceptions are logged but not re-raised.
    """
    try:
        user_id = message.get('user', '')
        text = message.get('text', '')
        ts = message.get('ts', '')

        if not text or not ts:
            return

        # Only process messages from OpenClaw bot
        if user_id not in OPENCLAW_USER_IDS:
            return

        status = detect_status(text)
        if not status:
            return

        project_name = extract_project_name(text)
        published_at = datetime.utcfromtimestamp(float(ts))

        cur.execute('''
            INSERT INTO project_updates (project_name, status, update_text, published_at)
            VALUES (%s, %s, %s, %s)
        ''', (project_name, status, text, published_at))
        conn.commit()

        log.info(f'Detected OpenClaw update: project="{project_name}" status={status}')

    except Exception as e:
        log.warning(f'openclaw_listener failed for message {message.get("ts")}: {e}')
