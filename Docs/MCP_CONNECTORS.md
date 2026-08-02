# MCP Connectors Setup Guide

How to enable **MCP** (Model Context Protocol) connectors in Second-Brain-App so
JIRA, Confluence, GitHub, Gmail, and Google Chat sync into your vault and appear
in Ask with citations.

Prefer MCP connectors over legacy HTTP types when both exist. Legacy token
connectors (`github`, `jira`, `confluence`, `slack`) still work; this guide covers
**MCP only**.

---

## Overview

```text
Settings / .env  →  MCP server Connect (OAuth or token)
                         ↓
              Add sync connector (mcp_jira, mcp_github, …)
                         ↓
              Test → Sync now → Ask about synced items
```

| MCP server (UI card) | Sync connector types | Auth |
|---|---|---|
| **Atlassian (JIRA + Confluence)** | `mcp_jira`, `mcp_confluence` | Browser OAuth (preferred) or Atlassian API token |
| **GitHub** | `mcp_github` | PAT in UI (preferred) or GitHub OAuth App |
| **GitHub Enterprise** | `mcp_github` | Self-hosted `github-mcp-server` + PAT / OAuth on GHES |
| **Google Workspace** | `mcp_gmail`, `mcp_gchat` | Google login via workspace-mcp OAuth 2.1 |
| **Custom MCP** | `mcp_custom` | OAuth, token, or none |

**Shared callback (most browser OAuth flows):**

```text
MCP_OAUTH_REDIRECT_URI=http://localhost:8000/mcp/oauth/callback
```

After code or UI changes, rebuild:

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head   # if migrations pending
```

---

## Common prerequisites

1. Stack running (`docker compose up -d`) with Postgres + API.
2. Open the app → **Knowledge ▸ Connectors**.
3. Top section: **MCP servers**. Bottom section: sync connectors.
4. Secrets can live in **Settings** (masked, same pattern as LLM keys) or `.env`.
   **Env always wins** over Settings if both are set.
5. Tokens are **never** stored on the connector row.

---

## 1. Atlassian (JIRA + Confluence)

### Extra settings required?

| Mode | Extra setup |
|---|---|
| **Connect (OAuth)** | None in `.env` beyond optional `MCP_OAUTH_REDIRECT_URI`. First Connect opens Atlassian login (Dynamic Client Registration). |
| **Use API token** | `JIRA_API_TOKEN` + Atlassian **account email** (UI field or `JIRA_EMAIL` / `ATLASSIAN_EMAIL`). |

### Steps (OAuth — recommended)

1. In **MCP servers**, open **Atlassian (JIRA + Confluence)**.
2. Click **Connect** → finish Atlassian consent in the browser tab.
3. Wait until the card shows **Connected**.
4. **Add connector**:
   - **JIRA (MCP):** project key (e.g. `ENG`); optional JQL / Cloud ID.
   - **Confluence (MCP):** space key; optional Cloud ID.
5. **Test** → **Sync now**.

### Steps (API token)

1. Create an [Atlassian API token](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Settings → **Connector credentials** → save **JIRA** token, **or** paste it on the Atlassian MCP card.
3. Enter your Atlassian **account email** on the card.
4. Click **Use API token**.
5. Add `mcp_jira` / `mcp_confluence` connectors as above.

### Optional env

```bash
# MCP_OAUTH_REDIRECT_URI=http://localhost:8000/mcp/oauth/callback
# JIRA_API_TOKEN=...
# JIRA_EMAIL=you@company.com
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| Test: missing tools / wrong tool names | Rebuild API image (tool names must be Rovo camelCase). |
| Sync fails after OAuth | Ensure Cloud ID resolves (optional `cloud_id` on connector, or reconnect). |
| Token Connect 401 | Personal tokens need **Basic email:token**; paste email + token, not Bearer-only. |

---

## 2. GitHub (github.com)

### Extra settings required?

| Mode | Extra setup |
|---|---|
| **Use API token** (recommended) | GitHub PAT (`repo` scope for private repos). Paste on the MCP card or Settings. |
| **OAuth (needs GitHub App)** | Register a [GitHub OAuth App](https://github.com/settings/developers); set client id/secret in `.env`. Remote GitHub MCP does **not** support Dynamic Client Registration. |

### Steps (PAT — recommended)

1. Create a fine-grained or classic PAT with access to the repos you will sync.
2. On the **GitHub** MCP card, paste the PAT → **Use API token**.
3. **Add connector → GitHub (MCP):** `owner/repo`; optional “include issues”.
4. **Test** → **Sync now**.

### Steps (OAuth App)

1. GitHub → Settings → Developer settings → **OAuth Apps** → New.
2. Authorization callback URL: `http://localhost:8000/mcp/oauth/callback`.
3. In `.env`:

```bash
GITHUB_OAUTH_CLIENT_ID=...
GITHUB_OAUTH_CLIENT_SECRET=...
# GITHUB_OAUTH_SCOPES=repo read:org read:user user:email
MCP_OAUTH_REDIRECT_URI=http://localhost:8000/mcp/oauth/callback
```

4. Recreate API: `docker compose up -d --build`.
5. On the GitHub card → **OAuth (needs GitHub App)**.

### Optional env

```bash
GITHUB_TOKEN=ghp_...   # or save via UI Settings / MCP card
```

---

## 3. GitHub Enterprise Server / ghe.com

Remote Copilot MCP (`api.githubcopilot.com`) does **not** support GHES. You need a
**self-hosted** [`github-mcp-server`](https://github.com/github/github-mcp-server)
pointed at your enterprise host.

### Extra settings required

```bash
# Enterprise web host (OAuth + links)
GITHUB_HOST=https://github.company.com

# REST API (optional; defaults to {GITHUB_HOST}/api/v3)
# GITHUB_API_URL=https://github.company.com/api/v3

# Self-hosted MCP endpoint (required for MCP card)
GITHUB_MCP_URL=http://localhost:8080/mcp

# PAT from your GHES instance
GITHUB_TOKEN=...

# Optional browser OAuth: register OAuth App ON THE ENTERPRISE HOST
# GITHUB_OAUTH_CLIENT_ID=...
# GITHUB_OAUTH_CLIENT_SECRET=...
# Callback = MCP_OAUTH_REDIRECT_URI
```

### Steps

1. Run `github-mcp-server` with `--gh-host https://github.company.com` (and token or OAuth client).
2. Set `GITHUB_HOST`, `GITHUB_MCP_URL`, `GITHUB_TOKEN` in `.env`; recreate stack.
3. In UI, use **GitHub Enterprise (self-hosted MCP)**:
   - Paste MCP URL if not set via env.
   - Paste PAT → **Use API token**.
4. Add **GitHub (MCP)** connector with `owner/repo` (optional API base for docs only).

### Legacy alternative (no MCP)

**GitHub (legacy token)** connector: set **API base** to
`https://github.company.com/api/v3` (or leave blank if `GITHUB_HOST` is set) + PAT.

---

## 4. Google Workspace (Gmail + Chat)

Connect opens a **Google login** (org Workspace accounts supported) via the local
`workspace-mcp` sidecar with MCP OAuth 2.1.

### Extra settings required (mandatory)

1. [Google Cloud Console](https://console.cloud.google.com/) → project.
2. Enable **Gmail API** and **Google Chat API**.
3. Create OAuth client type **Web application**.
4. Authorized redirect URIs:
   - `http://localhost:8001/oauth2callback`
   - `http://localhost:8000/mcp/oauth/callback`
5. Put credentials in `.env` (needed by **both** `api` and `workspace-mcp`):

```bash
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8001/oauth2callback
MCP_ENABLE_OAUTH21=true
WORKSPACE_MCP_URL=http://host.docker.internal:8001/mcp
WORKSPACE_EXTERNAL_URL=http://localhost:8001
WORKSPACE_MCP_ENABLED_SERVICES=gmail,chat
MCP_OAUTH_REDIRECT_URI=http://localhost:8000/mcp/oauth/callback
```

You can also paste client id/secret under **Settings → Google Workspace OAuth**
(for the API process). **Still put the same values in `.env`** so the
`workspace-mcp` container receives them on recreate.

### Steps

1. Start the core stack, then the Google sidecar profile:
   ```bash
   docker compose up -d --build
   docker compose --profile mcp up -d workspace-mcp
   ```
   Image default: `ghcr.io/taylorwilsdon/google_workspace_mcp:latest`
   (override with `WORKSPACE_MCP_IMAGE` if needed).
2. Confirm sidecar: `curl -sS http://127.0.0.1:8001/mcp` (or check `docker compose --profile mcp ps`).
3. MCP servers → **Google Workspace** → **Connect** → complete Google consent.
4. Add connectors:
   - **Gmail (MCP):** Gmail query / label (e.g. `in:inbox`).
   - **Google Chat (MCP):** Chat space ID.
5. **Test** → **Sync now**.

### Troubleshooting

| Symptom | Fix |
|---|---|
| Sidecar not reachable | `docker compose --profile mcp up -d workspace-mcp`; URL uses port **8001** on the host. |
| `pull access denied` for workspace-mcp | Use the GHCR default above; do not use `uspacy/workspace-mcp`. |
| Connect: missing client id | Set `GOOGLE_OAUTH_*` in `.env` and recreate. |
| Old card stuck on “none” auth | **Disconnect** the Google MCP server and Connect again (re-registers as `oauth`). |
| Popup blocked | Use the “Open sign-in link” fallback on the card. |

---

## 5. Custom MCP server

### Extra settings

- MCP **URL** (streamable HTTP).
- Auth mode: **OAuth**, **API token (env)**, or **None**.
- If token mode: name of env var holding the bearer token (set in Settings or `.env`).

### Steps

1. MCP servers → **Custom server** → name, URL, auth mode → Save.
2. Connect (OAuth popup or token verify).
3. Add **Custom MCP tool** connector: map `tool_name`, `items_path`, field paths as needed.

---

## 6. After MCP is connected — sync connectors

For every MCP type:

1. Card shows **Connected** / Ready for sync.
2. **Add connector** with the matching type (`mcp_*`).
3. Pick sync schedule (Manual / 15 min / Hourly / 6h / Daily).
4. **Test**, then **Sync now**.
5. Use **Ask about synced items** or Ask in the main chat.

Synced files land under:

```text
raw/connectors/<connector_type>/<resource_id>/<external_id>.md
```

---

## Env cheat sheet

| Variable | Used by |
|---|---|
| `MCP_OAUTH_REDIRECT_URI` | App OAuth callback (Atlassian, GitHub App, Google MCP client) |
| `JIRA_API_TOKEN` / `JIRA_EMAIL` | Atlassian token mode |
| `GITHUB_TOKEN` | GitHub / GHES PAT |
| `GITHUB_OAUTH_CLIENT_ID` / `SECRET` | GitHub browser OAuth only |
| `GITHUB_HOST` / `GITHUB_API_URL` / `GITHUB_MCP_URL` | Enterprise |
| `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` | Google Workspace (api + workspace-mcp) |
| `GOOGLE_OAUTH_REDIRECT_URI` | Sidecar ↔ Google callback (`:8001`) |
| `WORKSPACE_MCP_URL` / `WORKSPACE_EXTERNAL_URL` | Gmail/Chat MCP endpoint |
| `WORKSPACE_MCP_IMAGE` | Sidecar image (default GHCR `taylorwilsdon/google_workspace_mcp`) |
| `MCP_ENABLE_OAUTH21` | Must be `true` on workspace-mcp |

Full commented template: [`.env.example`](../.env.example).

---

## Related docs

- User install & legacy connectors: [`INSTRUCTIONS.md`](INSTRUCTIONS.md)
- Architecture (MCP vs legacy): [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Repo quickstart: [`../README.md`](../README.md)
