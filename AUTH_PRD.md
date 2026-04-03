# MCC Auth PRD — Full Clerk Authentication

**Status:** Planned (auth temporarily removed for demo)  
**Owner:** Bullseye  
**Target:** Add before public/team rollout

---

## Context

Auth was partially wired — Clerk env vars added to Netlify and Railway, backend verification added to `main.py` — but the frontend was never integrated. This caused a broken redirect loop after login. Auth has been stripped out for demo purposes. This PRD covers the complete re-implementation.

---

## What Was Removed (and Needs to Come Back)

### Backend (`backend/main.py`)
- `CLERK_SECRET_KEY` + `ALLOWED_DOMAIN` constants
- `verify_clerk_token()` async dependency function
  - Reads `Authorization: Bearer <token>` header
  - Calls `https://api.clerk.com/v1/tokens/verify`
  - Enforces `@gauntlethq.com` email domain
  - Skips `/api/health`
- `dependencies=[Depends(verify_clerk_token)]` on the FastAPI app constructor
- `httpx` import (used only for Clerk token verification)

### Railway Env Vars (still set, just unused)
- `CLERK_SECRET_KEY` — already in Railway

### Netlify Env Vars (still set, just unused)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`

---

## What Needs to Be Built (Frontend — Never Existed)

### 1. Install `@clerk/nextjs`
```bash
npm install @clerk/nextjs
```

### 2. Wrap app in `<ClerkProvider>` (`app/layout.tsx`)
```tsx
import { ClerkProvider } from '@clerk/nextjs'

export default function RootLayout({ children }) {
  return (
    <ClerkProvider afterSignInUrl="/" afterSignUpUrl="/">
      <html lang="en">
        <body>...</body>
      </html>
    </ClerkProvider>
  )
}
```

### 3. Create `app/sign-in/[[...sign-in]]/page.tsx`
```tsx
import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn />
    </div>
  )
}
```

### 4. Create `middleware.ts` (at repo root, not inside `app/`)
```ts
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isPublicRoute = createRouteMatcher(['/sign-in(.*)'])

export default clerkMiddleware((auth, req) => {
  if (!isPublicRoute(req)) auth().protect()
})

export const config = {
  matcher: ['/((?!_next|.*\\..*).*)'],
}
```

### 5. Inject auth token into all API calls (`lib/api.ts`)

Replace the bare `apiFetch` with a token-aware version:

```ts
import { useAuth } from '@clerk/nextjs'

// For use inside React components:
export function useApiClient() {
  const { getToken } = useAuth()
  return async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
    const token = await getToken()
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`API error ${res.status}: ${text}`)
    }
    return res.json()
  }
}
```

All pages (`page.tsx`, `history/page.tsx`) need to be refactored to use `useApiClient()` instead of calling the module-level functions directly.

### 6. Fix Clerk Dashboard — Paths config

In the Clerk Dashboard for app `special-oyster-86`:
- **Sign-in URL:** `https://marketing-command-center-55ff2635.netlify.app/sign-in`
- **Sign-up URL:** `https://marketing-command-center-55ff2635.netlify.app/sign-in` (same, no public sign-up)
- **After sign-in URL:** `https://marketing-command-center-55ff2635.netlify.app`
- **After sign-up URL:** `https://marketing-command-center-55ff2635.netlify.app`

This is the root cause of the current broken redirect — must be set before re-enabling auth.

### 7. Restrict to `@gauntlethq.com` domain only

Option A: Let the backend enforce it (already implemented in `verify_clerk_token`).  
Option B: Also add an allowlist in Clerk Dashboard → Restrictions → Email domain allowlist → `gauntlethq.com`.  
Do both for defense in depth.

---

## Re-enable Backend Auth

Once frontend is wired:
1. Restore `verify_clerk_token` function in `main.py`
2. Restore `dependencies=[Depends(verify_clerk_token)]` on the app
3. Restore `httpx` import
4. Deploy to Railway

---

## Deploy Checklist

- [ ] `npm install @clerk/nextjs` in `frontend/`
- [ ] `app/layout.tsx` — wrap in `ClerkProvider` with correct `afterSignInUrl`
- [ ] `app/sign-in/[[...sign-in]]/page.tsx` — add sign-in page
- [ ] `middleware.ts` — protect all routes except `/sign-in`
- [ ] `lib/api.ts` — inject Bearer token into all requests
- [ ] `app/page.tsx` + `app/history/page.tsx` — use `useApiClient()` hook
- [ ] Clerk Dashboard — set Paths (sign-in URL, after sign-in URL)
- [ ] Clerk Dashboard — add `@gauntlethq.com` to email allowlist
- [ ] `backend/main.py` — restore `verify_clerk_token` + `Depends`
- [ ] Railway deploy
- [ ] Netlify deploy
- [ ] End-to-end test: log in with `@gauntlethq.com` Google account → lands on app → query works

---

## Clerk App Details

- **Instance:** `special-oyster-86.clerk.accounts.dev` (dev instance)
- **App ID:** `app_3Boq8v3YG1Ce2j1wOy0eOnLDMHc`
- **Publishable key:** `pk_test_c3BlY2lhbC1veXN0ZXItODYuY2xlcmsuYWNjb3VudHMuZGV2JA`
- **Secret key:** in `~/.openclaw/secrets/clerk.json` and Railway/Netlify env
- **Google OAuth:** already enabled in Clerk

---

*Created: 2026-04-03. Implement when ready to lock down the app.*
