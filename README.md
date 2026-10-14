# InvoSync — Invoice & Delivery Challan Management Portal

A web-based portal for managing invoices and delivery challans for SK Agro, SK Electricals, and Triotech,
with Azure AI document extraction, Google Sheets sync, and Microsoft Teams notifications.

---

## Table of Contents
1. [How to Run Locally](#run-locally)
2. [How to Deploy to Render](#deploy)
3. [Database — Where Data Lives](#database)
4. [How to Roll Back](#rollback)
5. [Deploy Checklist (Every Time)](#checklist)
6. [How to Verify the Live Version](#verify)

---

## 1. How to Run Locally

### Prerequisites
- Python 3.10+
- pip

### Steps
```bash
# 1. Clone the project (if starting fresh)
git clone https://github.com/Muskangupta2007/invoice-processor.git
cd invoice-processor

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python app.py
# OR with gunicorn:
gunicorn --workers 1 --threads 4 --timeout 120 -b 0.0.0.0:5000 app:app
```

Open your browser to: http://localhost:5000

- Default login: `admin` / `invosync2026`
- The local database (`invoices.db`) is created automatically on first run.
- Excel files (SK_Agro.xlsx, etc.) are written to the project root by default.

---

## 2. How to Deploy to Render

Every change must go through: **edit → commit → push → verify**.

```bash
# 1. Make your code changes

# 2. Stage all changed files
git add -A

# 3. Commit with a clear message
git commit -m "Brief description of what you changed"

# 4. Push to GitHub (Render deploys automatically)
git push origin main

# 5. Watch the Render dashboard for deploy success
# 6. Verify the live site (see section 5 below)
```

### Setting Up Render for the First Time
1. Go to https://render.com -> New -> Web Service
2. Connect your GitHub repo (`invoice-processor`)
3. Set:
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command:** `gunicorn --workers 1 --threads 4 --timeout 120 -b 0.0.0.0:$PORT app:app`
4. Add Environment Variables (see Database section below)

---

## 3. Database — Where Data Lives

> **IMPORTANT:** Render has an ephemeral filesystem. SQLite files are wiped on every restart.
> **You MUST use a persistent PostgreSQL database in production.**

### Setting Up Supabase (Free, Recommended)

1. Go to https://supabase.com -> New Project (free tier)
2. Wait for the project to be created (~2 minutes)
3. Go to **Project Settings -> Database -> Connection string -> URI**
4. Copy the URI (it looks like: `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`)
5. In Render Dashboard -> Your Service -> Environment -> Add Environment Variable:
   - Key: `DATABASE_URL`
   - Value: *(paste the Supabase URI)*
6. Redeploy. The app will automatically use PostgreSQL instead of SQLite.

### Other Required Environment Variables (Render)
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase/PostgreSQL connection URL (required for persistent data) |
| `SECRET_KEY` | A random secret string for session tokens (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |

### Optional Environment Variables
| Variable | Description |
|----------|-------------|
| `AZURE_ENDPOINT` | Azure Document Intelligence endpoint URL |
| `AZURE_API_KEY` | Azure Document Intelligence API key |
| `TEAMS_WEBHOOK_URL` | Microsoft Teams incoming webhook URL |

### Local Development
- Locally, `invoices.db` (SQLite) is used automatically.
- It is excluded from git (`.gitignore`) -- this is correct.
- To back up locally: copy `invoices.db` somewhere safe before making risky changes.

---

## 4. How to Roll Back

### Roll Back Code
```bash
# See recent commits
git log --oneline -10

# Roll back to a specific commit (replace COMMIT_HASH with the hash from git log)
git revert COMMIT_HASH
git push origin main
# This creates a new "undo" commit and redeploys safely.

# OR to hard-reset (CAUTION: erases uncommitted work)
git reset --hard COMMIT_HASH
git push origin main --force
```

### Roll Back Data (PostgreSQL/Supabase)
Supabase provides automatic daily backups (Pro plan) and point-in-time recovery.
For the free plan, take manual backups regularly:
```bash
# Export from Supabase (replace values with your connection details)
pg_dump "postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres" > backup_$(date +%Y%m%d).sql

# Restore
psql "postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres" < backup_20261014.sql
```

### Roll Back Data (SQLite, local only)
```bash
# Backup before risky operations
cp invoices.db invoices_backup_$(date +%Y%m%d).db

# Restore
cp invoices_backup_20261014.db invoices.db
```

---

## 5. Deploy Checklist (Every Time)

Before every deploy, run through this list:

- [ ] All changes are committed: `git status` shows clean
- [ ] Changes are pushed: `git push origin main`
- [ ] Render deploy succeeded (green in dashboard)
- [ ] Visit `/health` on the live site -- `"status": "ok"`
- [ ] Visit `/api/version` -- confirm `git_commit` matches your latest push
- [ ] Log in and spot-check one invoice or challan
- [ ] If settings were changed, verify them in the Settings panel

---

## 6. How to Verify the Live Version

After every deploy, open these URLs (replace with your Render domain):

```
https://your-app.onrender.com/health
```
Expected response:
```json
{
  "status": "ok",
  "database": "postgresql",
  "database_ok": true,
  "document_count": 142,
  "git_commit": "050536c",
  "build_timestamp": "2026-10-14 14:45:00 UTC",
  "version": "InvoSync v1.0"
}
```

```
https://your-app.onrender.com/api/version
```

If `database_ok` is `false` or `database` shows `sqlite (local)`, the `DATABASE_URL` env var is missing or wrong.

---

## Project Structure

```
invoice-processor/
├── app.py              # Flask web server, all API routes
├── db.py               # Database layer (SQLite + PostgreSQL support)
├── gsheet.py           # Google Sheets push/pull sync
├── extractor.py        # Azure Document Intelligence PDF extraction
├── teams.py            # Microsoft Teams webhook notifications
├── gunicorn.conf.py    # Gunicorn production config
├── render.yaml         # Render deployment config
├── requirements.txt    # Python dependencies
├── static/
│   ├── index.html      # Main SPA frontend
│   └── app.js          # Frontend JavaScript
└── uploads/            # Temporary PDF uploads (ephemeral, not in git)
```

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Data disappears after restart | No `DATABASE_URL` set on Render | Add Supabase `DATABASE_URL` to Render env vars |
| Changes not visible on live site | Code not committed/pushed | Run `git add -A && git commit -m "..." && git push` |
| Old UI after deploy | Browser cache | Hard refresh: Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac) |
| Login fails on live site | `SECRET_KEY` not set | Add `SECRET_KEY` env var on Render |
| Google Sheets sync not working | Apps Script URL not saved in Settings | Log in -> Settings -> Configure Google Sheet URLs |