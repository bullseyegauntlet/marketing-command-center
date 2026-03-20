# Task Group 2 Prompt — Ingestion Pipelines

You are building the Marketing Command Center (MCC) for Gauntlet AI. Read SCHEMA.md, CHANGELOG.md, and .env to understand the project and credentials before starting.

Your job is Task Group 2: Ingestion Pipelines. Build all three ingestion pipelines. They can be developed in parallel but must all pass their tests before this group is done.

All credentials are in the .env file at the repo root. Use python-dotenv to load them.

---

**2.1 Slack Ingestion Pipeline**
Create /backend/ingestion/slack_ingestion.py

Core logic:
- Load SLACK_BOT_TOKEN, SLACK_CHANNEL_IDS (comma-separated), DATABASE_URL from .env
- Read checkpoint from ingestion_checkpoints table (source = 'slack')
- For each channel, call Slack conversations.history API with oldest = last checkpoint timestamp
- For each message, fetch full thread replies via conversations.replies
- Deduplicate: skip any message whose Slack ts is already in posts.external_id
- Normalize: extract links from message text, convert ts to UTC timestamp, construct source_url as https://gauntlet-ai.slack.com/archives/{channel_id}/p{ts_without_dot}
- Generate embedding via OpenAI text-embedding-3-small (batch efficiently)
- Insert into posts table (platform = 'slack')
- Update checkpoint after successful run
- Idempotent, retry with exponential backoff (3 attempts), dead letter logging to /backend/logs/dead_letter.json
- On 2+ consecutive_failures, post alert to SLACK_ALERT_CHANNEL via chat.postMessage

Create /backend/scripts/slack_backfill.py:
- Same logic but starts from beginning of channel history (ignores checkpoint)
- Paginates through all history
- Logs progress per channel

**2.2 X (Twitter) Ingestion Pipeline**
Create /backend/ingestion/x_ingestion.py

Core logic:
- Load X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, X_LIST_ID from .env
- Use OAuth 1.0a (requests_oauthlib)
- Read checkpoint from ingestion_checkpoints (source = 'x')
- Call GET /2/lists/{X_LIST_ID}/tweets with tweet.fields=created_at,public_metrics,entities and expansions=author_id,attachments.media_keys
- Paginate using pagination_token
- Deduplicate on external_id (tweet ID)
- Normalize: extract links from entities.urls, construct source_url as https://x.com/{username}/status/{tweet_id}, convert created_at to UTC
- Map public_metrics to likes, retweets, replies columns
- Generate embedding via OpenAI text-embedding-3-small
- Insert into posts (platform = 'x', channel = 'gauntlet_graduates')
- Update checkpoint
- Same reliability patterns: idempotent, retry, dead letter, alerting
- Respect 429s via Retry-After header

**2.3 OpenClaw Project Update Listener**
Create /backend/ingestion/openclaw_listener.py

- Runs as part of the Slack ingestion (not separate cron)
- After inserting a Slack message into posts, check if it matches the OpenClaw update pattern
- OpenClaw updates follow this format (detect by author being the bot or specific keywords):
  - Contains status keywords: "on track", "at risk", "blocked", "completed"
  - And a project name pattern
- If detected: also insert into project_updates table with parsed project_name, status, update_text
- This is best-effort — failures here should not block Slack ingestion

**2.4 Integration Tests**
Create /backend/tests/test_slack_ingestion.py — mock Slack API responses, test: correct insertion, deduplication, checkpoint updates, error handling
Create /backend/tests/test_x_ingestion.py — mock X API responses, same tests
Create /backend/tests/test_openclaw_listener.py — test project update parsing

Use pytest + unittest.mock. Tests should run without hitting real APIs.

**2.5 Deploy and First Run**
- Run slack_backfill.py for all 3 channels and log results
- Run x_ingestion.py once manually and verify data in DB
- Verify embeddings and tsvectors are populated for all records
- Commit everything to git with clear commit messages

**Also:**
- Create /backend/logs/ directory with .gitkeep
- Update CHANGELOG.md with what you built
- Update requirements.txt if new deps added

When completely finished run: openclaw system event --text "Done: Task Group 2 complete — Slack and X ingestion pipelines built, backfill run, data in DB" --mode now
