# Instagram Publishing — Progress & Context

> **Purpose:** Pick-up doc for Tirth / collaborator. Everything below was done and
> verified on 2026-10-16. Read this first before touching the Instagram flow.
>
> **Status:** 🟡 Diagnosis complete, fix plan agreed, implementation NOT started.
> **Agreed route:** Official Instagram Graph API (Business/Creator account).
> **Fallback route (if API route fails):** Claude/Playwright browser automation — see
> [Option B](#option-b-clausebrowser-automation-fallback) at the end.

---

## 1. What the feature is supposed to do

User flow in the web app:

1. Generate a caption (AI pipeline) for a photo.
2. Go to Dashboard → **Post to Social** → select generated post (photo) + connected
   Instagram account.
3. Frontend `postToSocial()` in `templates/dashboard.html` (~line 917) POSTs
   `/api/social/post-now` with `account_id, caption, hashtags, media_path, media_type`.
4. Backend `app/api/social.py::post_now` (~line 1186) → `InstagramProvider.publish_post()`
   (`app/social/providers/instagram.py:212`) → media container → poll → publish →
   permalink returned to UI.

**It does not work today.** See §3 for why.

---

## 2. Work already completed (2026-10-16)

### 2.1 Repo sync
- Collaborator had pushed to **`origin/master`** while local **`main`** was behind.
- Local `main` was a strict ancestor → fast-forwarded `main` to `8569e15`.
- New commits pulled in (from collaborator Tirth Patel):
  - `e5e0073` Add workflow management, social posting improvements, and n8n integration
  - `2028fd4` Update Tech Stack section header in README
  - `11e3b99` Merge pull request #1
  - `8569e15` feat(social): add direct Instagram token integration
- ⚠️ Note: repo `HEAD` is `origin/master`; local `main` tracks `origin/main`.
  Consider consolidating to one default branch.

### 2.2 Test / error audit of the pulled commits
| Finding | Severity | Detail |
|---|---|---|
| `tests/test_workflows.py::test_local_scheduler_skips_active_n8n_posts` **FAILS** | **Real bug in committed test** | `sqlalchemy OperationalError: no such table: workflow_jobs`. Root cause: test writes fixtures via `TestSessionLocal` (test DB) but queries `RealSessionLocal` (real `contentai.db`) at `tests/test_workflows.py:242`. Wrong DB → test is broken/meaningless. **Fix: query `TestSessionLocal`.** Introduced in `e5e0073`. |
| `tests/test_posts.py::test_upload_image_jpeg` **HANGS** | Environment, not code | Image pipeline downloads BLIP captioning model (`Salesforce/blip-image-captioning-base`, ~1GB) which is not cached → stalls on network. Pre-existing. |
| `TestHistory::test_empty_history` failed once | Flaky | Caused by stale rows in `test_contentai.db` left by the hung run. Passes after `del test_contentai.db`. Not a code bug. |
| `test_social.py` (20 passed), `test_auth.py` (14 passed) | ✅ | Green. |
| `python -m compileall app tests` | ✅ | exit 0, no syntax errors. |

- Tests must be run with **system Python** (`python -m pytest ...`): the project
  `venv` is missing `pytest`. Heavy ML imports are all lazy (inside functions), so
  collection is fast (~2.5s import of `app.main`).
- No linter configured (no ruff/flake8/pyflakes installed).

---

## 3. Why Instagram posting does not work (diagnosis — verified)

Four independent blockers; fixing any one alone is not enough.

### B1. Demo mode is ON → posts are faked, never sent to Instagram
- `.env`: `SOCIAL_DEMO_MODE=true`.
- "Connect Instagram" then creates a **simulated** account whose
  `platform_user_id = "demo_instagram"` (`_connect_demo_account`,
  `app/api/social.py:227`).
- `post_now` / `publish_now` / scheduler short-circuit to
  `demo_publish_result()` whenever `is_demo_account(account)` is true
  (`app/social/base.py`), returning a **fabricated** permalink
  `https://www.instagram.com/p/demo_<hex>/`. UI shows "Posted successfully!" but
  **nothing reaches Instagram**.
- Current `contentai.db` has **zero rows in `social_accounts`** — no connected
  account at all right now.

### B2. No live credentials
`.env` today (keys only, values omitted):

```
INSTAGRAM_CLIENT_ID        = <EMPTY>
INSTAGRAM_CLIENT_SECRET    = <EMPTY>
INSTAGRAM_REDIRECT_URI     = <SET, len 51>
INSTAGRAM_ACCESS_TOKEN     = (not present at all)
PUBLIC_BASE_URL            = http://localhost:8000
SOCIAL_DEMO_MODE           = true
```

No credentials → no OAuth path → demo path only (see B1).

### B3. Media URL must be publicly reachable (will bite even after B1/B2 fixed)
- `publish_post` validates the photo URL at
  `instagram.py:_validate_public_media_url` (~line 454):
  - rejects if `PUBLIC_BASE_URL` empty / contains `localhost` / `127.0.0.1`
  - rejects any URL not starting with `https://`
  - live-fetches the URL and checks content-type is `image/*`
- Instagram's servers must download the photo from a **public HTTPS** URL.
  The photo lives in `uploads/` served by the app on `http://localhost:8000` →
  **Instagram can never fetch it as configured.**
- `_media_url()` (instagram.py:511) blindly prefixes `PUBLIC_BASE_URL` onto
  relative `media_path`.

### B4. Instagram API account-type / token-type limits
- `InstagramProvider.supports_publishing()` (instagram.py:335) returns True only
  for `business` / `creator`. **Personal accounts cannot publish via any official
  API.** → User confirmed target profile is **Business/Creator** ✅ (so B4 is a
  non-issue for us).
- ⚠️ Token-type trap: `_api_host()` / `get_account_info()` route `IGQVJ…`/`IGAA…`
  tokens to `graph.instagram.com` (Basic Display / Instagram Login) — that API is
  **read-only, cannot publish**. Publishing requires a **Facebook-Login
  long-lived token** with `instagram_content_publish` scope, on a Professional
  account linked to a Facebook Page.

**Net: today the code can only fake-post (demo) or error out.**

---

## 4. Decisions made

- **Route chosen:** Option A — fix/implement the **official Graph API** flow.
  No ToS risk, works with the existing codebase.
- **Account type:** user's target profile is **Business / Creator** (confirmed).
- **Option B (Claude browser automation)** kept as documented fallback — see §7.

---

## 5. Implementation plan — Option A (official Graph API) — NOT STARTED

### Step 1 — Meta console setup (human task, ~15 min; we supply exact steps)
1. Link IG Professional account to a **Facebook Page**
   (`business.facebook.com` → Settings → Connected accounts).
2. Create app at `developers.facebook.com` → type **Business** → add products
   **Instagram Graph API** + **Facebook Login**.
3. Facebook Login → Settings → add Valid OAuth Redirect URI = the value already
   in `.env` `INSTAGRAM_REDIRECT_URI`.
4. Add yourself as a **test user** (unless app is Live).
5. Collect **App ID**, **App Secret**, and either:
   - a **long-lived user token** (Graph API Explorer → Get Token → User or Page
     token with scopes `instagram_basic, instagram_content_publish,
     pages_show_list, pages_read_engagement` → exchange to long-lived via
     `fb_exchange_token`), **or**
   - use the app's OAuth popup path already built
     (`InstagramProvider.get_oauth_url` / `exchange_code`).

### Step 2 — `.env` changes (code task)
```
SOCIAL_DEMO_MODE=false
INSTAGRAM_CLIENT_ID=<App ID>
INSTAGRAM_CLIENT_SECRET=<App Secret>
INSTAGRAM_ACCESS_TOKEN=<long-lived token>   # optional if using the OAuth popup
```
Both connect paths are implemented:
- **Token bootstrap:** `/api/social/connect/instagram` detects
  `INSTAGRAM_ACCESS_TOKEN` → `_import_instagram_token()` (`app/api/social.py:569`)
  — added by collaborator commit `8569e15`.
- **OAuth popup:** standard `/connect/{platform}` → `/callback` flow.

### Step 3 — Code changes required (the real gap)
1. **NEW media hosting step** (feature: `app/services/media_host.py` or similar):
   before creating the media container, upload `uploads/<file>` to a public HTTPS
   host (ImgBB or Cloudinary, free API key, one new config var e.g.
   `MEDIA_HOST_PROVIDER` + `IMGBB_API_KEY`) → returns a stable public HTTPS URL.
   This **eliminates the ngrok tunnel** entirely: only the *image* needs to be
   public, not the app.
2. `instagram.py` fixes:
   - `_media_url()` (line 511): if `media_path` already starts with `https://`,
     use it as-is (no `PUBLIC_BASE_URL` prefix).
   - `_validate_public_media_url()` (line 454): only enforce the
     `PUBLIC_BASE_URL`/localhost rules for **locally-hosted** URLs; externally
     hosted URLs are validated directly.
3. **Token-expiry fix:** `_import_instagram_token` sets `token_expires_at=None`,
   so `_maybe_refresh_token` (`app/api/social.py:83`) never fires → token dies
   silently after 60 days. Store `expires_in` (= 60 days for long-lived) so the
   silent refresh works (refresh uses `fb_exchange_token`, requires App ID/Secret).
4. Optional: surface the new hosting errors in the Dashboard post modal (UI
   already renders `error_message`, likely nothing to do).

### Step 4 — Verify end-to-end
1. Restart server.
2. Dashboard → Connect Instagram → must show real `@username`, `account_type`
   business/creator, NOT `demo_*`.
3. Generate caption → select photo → **Post** → expect real
   `https://www.instagram.com/p/...` permalink.
4. Confirm `posting_history` row + UI "Published posts" entry.
5. Keep `SOCIAL_DEMO_MODE=true` for the test suite (tests force it anyway in
   `tests/conftest.py`); add unit tests for the new media-URL/hosting logic.
6. Run `python -m pytest tests -q` (system Python; expect
   `test_workflows` failure below to be fixed too).

### Pre-existing fix to bundle in
- `tests/test_workflows.py:242` — use `TestSessionLocal` instead of
  `RealSessionLocal` (see §2.2).

---

## 6. Current `.env` inventory (safe keys — no secrets in this doc)

```
DATABASE_URL                     = <SET>
JWT_SECRET_KEY                   = <SET>
JWT_ALGORITHM                    = <SET>
ACCESS_TOKEN_EXPIRE_MINUTES      = <SET>
REFRESH_TOKEN_EXPIRE_DAYS        = <SET>
OLLAMA_HOST / OLLAMA_MODEL       = <SET>
UPLOAD_DIR                       = <SET>
CORS_ORIGINS                     = <SET>
INSTAGRAM_CLIENT_ID              = <EMPTY>      ← needs App ID
INSTAGRAM_CLIENT_SECRET          = <EMPTY>      ← needs App Secret
INSTAGRAM_REDIRECT_URI           = <SET len 51>
PUBLIC_BASE_URL                  = http://localhost:8000   ← localhost; only
                                   matters for locally-hosted media once
                                   Step-3 hosting lands (or use a tunnel)
SOCIAL_DEMO_MODE                 = true         ← flip to false for real posts
INSTAGRAM_ACCESS_TOKEN           = <absent>     ← optional long-lived token
```

---

## 7. Option B — Claude browser automation (FALLBACK if API route fails)

If the Meta app route stalls (app review, token, page-linking…), post directly by
driving a real browser. **Caveat first:** automating instagram.com violates IG's
ToS — automation of your own account risks action-blocks; treat as fallback /
personal-testing only, and prefer a dedicated/test profile.

### Architecture
- **Playwright MCP server** running against a **persistent browser profile**
  (so login session + 2FA survive restarts), e.g.:
  - `claude mcp add playwright -- npx @playwright/mcp@latest --storage-state
    ~/.ig-profile/state.json` (or `--user-data-dir` for full profile reuse).
- The project gains an outbound **automation poster** that does NOT log in itself;
  it only hands the job to the agent layer:
  1. App already knows `media_path` + generated `caption` + `hashtags`.
  2. Invoke headless Claude to perform the upload:
     ```
     claude -p "Open instagram.com, create a new photo post using file
     <ABS_MEDIA_PATH>, caption: <<CAPTION>>. Confirm the post URL." \
       --allowedTools "mcp__playwright__*" --permission-mode acceptEdits
     ```
  3. Store returned URL in `posting_history` exactly like the Graph API path
     (same `PostingHistory` row / same UI), so the UI is unchanged.
- Integration point: implement as an alternative `SocialProvider`-style strategy
  (e.g. `automation_publish()` in a new
  `app/social/providers/instagram_automation.py`) selected when
  `INSTAGRAM_PUBLISH_MODE=automation` in `.env`. Keeps `post_now` contract
  (`PublishResult`) intact.

### Flow steps to build
1. One-time interactive login: open instagram.com in headed Playwright → user
   logs in (2FA) → save `storage-state.json` into `~/.ig-profile/`.
2. `start_post`: goto `https://www.instagram.com/` → "Create" → "Post" →
   `set_input_files` on the file input with the photo → wait for preview →
   write caption into the contenteditable → "Next" → "Share".
3. Wait for the post to appear / capture the `https://www.instagram.com/p/<id>/`
   URL from the profile grid → return as `PublishResult(success=True, ...)`.
4. Rate-limit: ≥5–10 min between posts, avoid rapid repeat logins.

### Why keep it as fallback only
- Fragile selectors / IG UI churn; needs occasional re-verification.
- ToS & account-flag risk (§ caveat above).
- No reliable way to fetch metrics/delete — Graph API still needed for those.

**Switching between them is one env var** (`INSTAGRAM_PUBLISH_MODE`:
`api` | `automation`), so both routes can coexist.

---

## 8. TODO for next session (start here tomorrow)

- [ ] **Human:** do Meta console setup (§5 Step 1) — create app, get App ID/Secret,
      get long-lived token (or decide OAuth popup), link IG↔FB Page.
- [ ] **Human:** hand over App ID + App Secret + token; decide
      token-bootstrap vs OAuth popup.
- [ ] **Claude:** Step 2 `.env` edits (`SOCIAL_DEMO_MODE=false`, credentials).
- [ ] **Claude:** Step 3 code — media hosting + `_media_url` /
      `_validate_public_media_url` fixes + token-expiry fix.
- [ ] **Claude:** fix `tests/test_workflows.py:242` wrong-DB bug.
- [ ] **Claude:** run full test suite (system Python) + add unit tests for
      media hosting.
- [ ] **Both:** end-to-end real post verification (§5 Step 4).
- [ ] **Decide:** if API route fails → activate Option B (§7).

---

## 9. Quick file map (Instagram flow)

| File | Role |
|---|---|
| `templates/dashboard.html` (~917) | `postToSocial()` UI → POST `/api/social/post-now` |
| `app/api/social.py` | OAuth/connect, token import (`:569`), `post_now` (`:1187`), `publish_now` (`:1097`), demo connect (`:227`), silent refresh (`:83`) |
| `app/social/providers/instagram.py` | Graph API provider: `publish_post` (`:212`), URL validation (`:454`), `_media_url` (`:511`), `supports_publishing` (`:335`) |
| `app/social/base.py` | `is_demo_account` / `demo_publish_result` (fake-publish short-circuit) |
| `app/social/registry.py` | provider auto-registration, `platform_config_errors` (checks credentials + PUBLIC_BASE_URL) |
| `app/services/scheduler.py` | background publish loop (same provider path) |
| `tests/conftest.py` | forces `SOCIAL_DEMO_MODE=true` for tests |
| `tests/test_workflows.py:242` | ⚠️ broken wrong-DB test (fix) |
