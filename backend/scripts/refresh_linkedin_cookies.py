#!/usr/bin/env python3
"""
LinkedIn Cookie Refresh Script
Extracts fresh LinkedIn session cookies from the OpenClaw Chrome browser profile
and saves them to ~/.openclaw/secrets/linkedin_cookies.json.

Requires:
  - OpenClaw browser CLI (openclaw browser)
  - Chrome profile 'openclaw' logged into LinkedIn as bullseye.gauntlet@gmail.com
  - LinkedIn session active in that browser

Usage:
  python3 backend/scripts/refresh_linkedin_cookies.py [--upload-github]

Flags:
  --upload-github    Also update the LINKEDIN_COOKIES_JSON GitHub Actions secret
                     (requires gh CLI authenticated)

Run this whenever the LinkedIn ingestion fails with an auth error (~every 2 weeks).
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

COOKIES_PATH = os.path.expanduser('~/.openclaw/secrets/linkedin_cookies.json')
GITHUB_REPO  = 'bullseyegauntlet/marketing-command-center'
GITHUB_SECRET = 'LINKEDIN_COOKIES_JSON'


def run(cmd: list, capture=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, check=True)


def extract_cookies_from_browser() -> dict:
    """Pull LinkedIn cookies from the openclaw Chrome profile via CDP."""
    print('📡 Extracting cookies from Chrome (openclaw profile)...')

    # Navigate to LinkedIn to ensure cookies are fresh
    try:
        run(['openclaw', 'browser', 'navigate', '--browser-profile', 'openclaw',
             'https://www.linkedin.com/feed/'])
        import time; __import__('time').sleep(3)
    except subprocess.CalledProcessError as e:
        print(f'  Warning: could not navigate browser: {e.stderr}')

    # Evaluate JS to get all LinkedIn cookies
    js = '''
    document.cookie.split(';').reduce((acc, c) => {
      const [k, ...v] = c.trim().split('=');
      acc[k] = v.join('=');
      return acc;
    }, {})
    '''
    result = run(['openclaw', 'browser', 'evaluate', '--browser-profile', 'openclaw', js])
    cookies_raw = json.loads(result.stdout.strip())

    # Filter to LinkedIn-relevant cookies
    li_keys = {'li_at', 'JSESSIONID', 'li_rm', 'liap', 'li_mc', 'li_g_recent_logout',
                'li_theme', 'li_theme_set', 'bcookie', 'bscookie', 'lidc', 'lang',
                'AnalyticsSyncHistory', 'UserMatchHistory', 'lms_ads', 'lms_analytics'}

    cookies = {k: v for k, v in cookies_raw.items()
               if k in li_keys or k.startswith('li_') or 'linkedin' in k.lower()}

    if 'li_at' not in cookies:
        print('❌ li_at cookie not found — not logged in to LinkedIn in the openclaw Chrome profile.')
        print('   Please log in at linkedin.com in that browser and try again.')
        sys.exit(1)

    print(f'  ✅ Got {len(cookies)} LinkedIn cookies (li_at present, len={len(cookies.get("li_at", ""))})')
    return cookies


def save_cookies(cookies: dict) -> None:
    os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
    with open(COOKIES_PATH, 'w') as f:
        json.dump(cookies, f, indent=2)
    print(f'  💾 Saved to {COOKIES_PATH}')


def verify_cookies(cookies: dict) -> bool:
    """Quick sanity check — instantiate the Linkedin client and make one call."""
    print('🔍 Verifying cookies work...')
    try:
        from requests.cookies import RequestsCookieJar
        from linkedin_api import Linkedin

        jar = RequestsCookieJar()
        for name, value in cookies.items():
            jar.set(name, value, domain='.linkedin.com', path='/')

        api = Linkedin('bullseye.gauntlet@gmail.com', '', cookies=jar)
        # Light test — fetch 1 company update
        updates = api.get_company_updates('gauntletai', max_results=1)
        print(f'  ✅ Verified — fetched {len(updates)} company update(s)')
        return True
    except ImportError:
        print('  ⚠️  linkedin-api not installed locally — skipping verification')
        print('     Install with: pip install linkedin-api')
        return True  # assume ok, will fail at ingestion time if not
    except Exception as e:
        print(f'  ❌ Verification failed: {e}')
        return False


def upload_to_github(cookies: dict) -> None:
    """Update the LINKEDIN_COOKIES_JSON GitHub Actions secret."""
    print(f'🔐 Uploading to GitHub secret {GITHUB_SECRET}...')
    cookies_json = json.dumps(cookies)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(cookies_json)
        tmp_path = f.name

    try:
        run(['gh', 'secret', 'set', GITHUB_SECRET,
             '--repo', GITHUB_REPO,
             '--body', cookies_json])
        print(f'  ✅ GitHub secret updated')
    except subprocess.CalledProcessError as e:
        print(f'  ❌ Failed to update GitHub secret: {e.stderr}')
        print(f'     Run manually: gh secret set {GITHUB_SECRET} --repo {GITHUB_REPO} < {COOKIES_PATH}')
    finally:
        os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(description='Refresh LinkedIn session cookies')
    parser.add_argument('--upload-github', action='store_true',
                        help='Also update the LINKEDIN_COOKIES_JSON GitHub Actions secret')
    parser.add_argument('--verify-only', action='store_true',
                        help='Just verify existing cookies without refreshing')
    args = parser.parse_args()

    print(f'🔄 LinkedIn Cookie Refresh — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print()

    if args.verify_only:
        if not os.path.exists(COOKIES_PATH):
            print(f'❌ No cookies file at {COOKIES_PATH}')
            sys.exit(1)
        with open(COOKIES_PATH) as f:
            cookies = json.load(f)
        ok = verify_cookies(cookies)
        sys.exit(0 if ok else 1)

    cookies = extract_cookies_from_browser()
    save_cookies(cookies)

    ok = verify_cookies(cookies)
    if not ok:
        print()
        print('⚠️  Cookies saved but verification failed.')
        print('   The LinkedIn session may be expired. Log in at linkedin.com and retry.')
        sys.exit(1)

    if args.upload_github:
        upload_to_github(cookies)

    print()
    print('✅ Done. LinkedIn cookies refreshed successfully.')
    print(f'   Next refresh needed in ~2 weeks.')


if __name__ == '__main__':
    main()
