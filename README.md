# VectorOS

**VectorOS** is a complete GTM (Go-To-Market) engine with a web dashboard. It finds companies that look like your ideal customer, finds the decision-makers inside them, writes personalised outreach, sends it, reads the replies, and books meetings.

It has two halves that run at the same time:

| Half | Folder | What it is | Runs on |
|---|---|---|---|
| **Backend** (the brain) | `Vector/` | Python + FastAPI. AI agents, database, API. | http://localhost:8787 |
| **Frontend** (the screen) | `vector-crm/` | React + TypeScript + Vite. The dashboard you look at. | http://localhost:5273 |

You need **both running** to use the app. The frontend is just a window; the backend does the work.

---

# ⭐ START HERE — the 5-minute version

**Good news: you do NOT need any API keys, accounts, or paid services to see the app working.**

The app ships with a **demo workspace** — 47 fake companies and 102 fake people, already filled in. It builds itself automatically the first time you start the backend. No keys, no signup, no credit card.

You will open **two terminal windows** and leave them both running. Think of it like a lamp: one terminal is the power, the other is the bulb. Turn off either one and the app stops.

## Before you start: do you have the tools?

Copy-paste each line into your terminal and press Enter.

```bash
python3 --version    # need 3.11 or higher (e.g. "Python 3.12.1")
node --version       # need 18 or higher (e.g. "v20.11.0")
npm --version        # comes with Node (e.g. "10.2.4")
```

If any command says `command not found`, install the missing tool first:

- **Python** → https://www.python.org/downloads/ (during install on Windows, tick **"Add Python to PATH"**)
- **Node.js + npm** → https://nodejs.org/ (pick the **LTS** version)

Then **close and reopen your terminal** and check the versions again.

> **What is a terminal?**
> - **Mac** — press `Cmd + Space`, type `Terminal`, press Enter.
> - **Windows** — press the Start button, type `PowerShell`, press Enter.
> - **Linux** — press `Ctrl + Alt + T`.

---

## Terminal 1 — start the backend (the brain)

Run these **one line at a time**, waiting for each to finish before the next.

```bash
# 1. Go into the backend folder
cd VectorOS/Vector

# 2. Create a private box for Python packages (a "virtual environment")
python3 -m venv .venv

# 3. Switch into that box
source .venv/bin/activate
# 👆 On Windows PowerShell use this instead:
#    .venv\Scripts\Activate.ps1

# 4. Install everything the backend needs (takes 1-3 minutes)
pip install -r requirements.txt

# 5. Start it
python run_api.py
```

**✅ Success looks like this:**

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8787 (Press CTRL+C to quit)
```

**Now leave this window alone.** Do not close it. Do not press `Ctrl + C`. It looks like it's frozen — that's correct, it's waiting to answer requests.

> After step 3 works, your prompt gets a `(.venv)` prefix like `(.venv) you@laptop Vector %`. That's how you know you're inside the box.

**Quick check (optional):** open http://localhost:8787/api/health in your browser. You should see:
```json
{"status":"ok","service":"vector-api"}
```

---

## Terminal 2 — start the frontend (the screen)

Open a **brand-new terminal window** (`Cmd+N` on Mac, or a new PowerShell window). Leave Terminal 1 running.

```bash
# 1. Go into the frontend folder
cd VectorOS/vector-crm

# 2. Install everything it needs (takes 1-3 minutes)
npm install

# 3. Start it
npm run dev
```

**✅ Success looks like this:**

```
  VITE v5.3.4  ready in 412 ms

  ➜  Local:   http://localhost:5273/
```

> `npm install` may print warnings about "vulnerabilities" or "deprecated" packages. **This is normal.** Ignore it. Only a red `ERR!` means something actually broke.

---

## Open the app and log in

Go to **http://localhost:5273** in your browser.

You'll see a login screen. Use the demo account:

| | |
|---|---|
| **Email** | `demo@vector.ai` |
| **Password** | `demo1234` |

You're in. Click around the sidebar — Dashboard, People, Companies, Sequences, Analytics. Everything is filled with realistic sample data.

> **There is no "Sign up" button, and that's on purpose.** Accounts are created from the command line (see [Making your own account](#making-your-own-account)). The demo account above is created for you automatically.

---

## When you're done

Click on each terminal window and press **`Ctrl + C`** (hold Ctrl, press C). That stops the servers.

**Next time you come back, you skip the install steps.** You only need:

```bash
# Terminal 1
cd VectorOS/Vector && source .venv/bin/activate && python run_api.py

# Terminal 2
cd VectorOS/vector-crm && npm run dev
```

---

# 🛟 Something went wrong

Find your error message below.

### `command not found: python3`
Python isn't installed, or isn't on your PATH. Reinstall from [python.org](https://www.python.org/downloads/) and **tick "Add Python to PATH"**. Then reopen your terminal. On Windows, try `python` instead of `python3`.

### `No such file or directory: requirements.txt`
You're in the wrong folder. Run `pwd` (Mac/Linux) or `cd` (Windows) — the path must end in `/Vector`. Use `cd Vector` to get there, or `cd ..` to go up one level.

### `Address already in use` / `port 8787 is in use`
A copy of the backend is already running from earlier. Either use it, or kill it:

```bash
# Mac / Linux
lsof -ti:8787 | xargs kill -9

# Windows PowerShell
Get-NetTCPConnection -LocalPort 8787 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

Or just run it on a different port: `VECTOR_API_PORT=9000 python run_api.py` (then also set `VITE_API_URL` — see [Changing ports](#changing-ports)).

### `Network error — is the API server running?` (on the login page)
The frontend can't reach the backend. **This is the most common problem.**
1. Is Terminal 1 still open and running? Check it didn't crash or get closed.
2. Open http://localhost:8787/api/health — if it doesn't load, the backend is down. Restart it.
3. If you changed the backend port, see [Changing ports](#changing-ports).

### `Invalid email or password`
Type it exactly: `demo@vector.ai` and `demo1234`. No capitals, no spaces. If it still fails, rebuild the demo data:
```bash
cd Vector && source .venv/bin/activate
python -m backend.manage seed-demo --force
```

### `.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled`
Windows blocks scripts by default. Run this once, then retry:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `ModuleNotFoundError: No module named 'fastapi'` (or `backend`)
Two possible causes:
1. You forgot to activate the venv. Look for `(.venv)` in your prompt. Run `source .venv/bin/activate`.
2. You're in the wrong folder. All Python commands must run from inside `Vector/`, not from `VectorOS/`.

### `npm ERR! code ENOENT` / `package.json not found`
You're not in the `vector-crm` folder. Run `cd vector-crm` first.

### The page is blank / white
Hard-refresh: `Cmd + Shift + R` (Mac) or `Ctrl + Shift + R` (Windows). If still blank, open the browser console (`F12`) and read the red error.

### Nothing works and I want to start completely fresh
This deletes all local data and reinstalls. Safe — nothing on GitHub is touched.
```bash
cd VectorOS/Vector
rm -rf .venv data/vector.db data/vector.db-shm data/vector.db-wal
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python run_api.py

# in Terminal 2
cd VectorOS/vector-crm && rm -rf node_modules && npm install && npm run dev
```

---

# 🔐 Is it safe? (Read this before adding API keys)

**Yes — by default VectorOS cannot email anyone, message anyone, or spend any money.**

It boots in **SAFE mode**. Emails are printed to your terminal instead of sent. LinkedIn and Calendar use fake "mock" providers. Verify it yourself:

```bash
cd Vector && source .venv/bin/activate
python -m backend.manage config
```

You'll see:

```
  MODE: SAFE (dry-run email · mock LinkedIn · mock calendar)

  Safety / providers
    PULSE_LIVE            = False
    CONNECT_PROVIDER      = mock
    CALENDAR_PROVIDER     = mock
    EMAIL_DRY_RUN         = True
```

`modules/common/control.py` is the single control panel for every switch in the engine. One master switch, `VECTOR_PULSE_LIVE`, governs all real-world sending. While it is `false`, nothing leaves your laptop.

> ⚠️ **Only set `VECTOR_PULSE_LIVE=true` when you genuinely intend to email real strangers.** That sends real messages from your real mailbox, which affects your domain's reputation and may be regulated where you live (CAN-SPAM, GDPR). Leave it `false` while learning.

---

# 🚀 Level 2 — running the real AI engine

Everything above used pre-made demo data and needed no keys. To make VectorOS actually go out and find real companies, you need an AI API key.

## Step 1 — create your `.env` file

`.env` is a private file holding your secret keys. It is **gitignored** — it will never be uploaded to GitHub.

```bash
cd VectorOS/Vector
cp .env.example .env
```

Now open `Vector/.env` in any text editor.

## Step 2 — add one key

The **only** required key is an AI provider. Pick one:

| Provider | Variable | Get a key from |
|---|---|---|
| **Anthropic (Claude)** — recommended | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| Google (Gemini) | `GOOGLE_API_KEY` | https://aistudio.google.com/apikey |

Find the line and paste your key after the `=` — no quotes, no spaces:

```env
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
DEFAULT_LLM_PROVIDER=claude
```

> 💡 Every other key in `.env.example` is **optional**. Apollo, PDL, Google Search, PhantomBuster, Unipile — all have free fallbacks and can stay empty. Start with just the one AI key.

> 🔒 **Never** paste a real key into `.env.example`, a README, a screenshot, or a chat message. Only `.env`.

## Step 3 — make a live account

The demo account is deliberately blocked from running the real engine (so you can't spend money by accident). Make a real one:

```bash
cd VectorOS/Vector && source .venv/bin/activate

python -m backend.manage create-account \
  --email you@yourcompany.com \
  --password pick-a-password \
  --name "Your Name"
```

## Step 4 — run the pipeline

```bash
python -m backend.manage run-pipeline --email you@yourcompany.com --max-leads 3
```

This takes a few minutes and prints its progress. Start with `--max-leads 3` — each lead costs AI tokens. Then log into the dashboard with your new account to see the real companies it found.

> The engine is still in SAFE mode, so it will research and draft outreach but **not send** it. That's the right way to inspect the output first.

---

# 🧰 Command cheat-sheet

All of these run from inside `Vector/` with the venv activated (`source .venv/bin/activate`).

| Command | What it does |
|---|---|
| `python run_api.py` | Start the backend API |
| `VECTOR_API_PORT=9000 python run_api.py` | Start it on a different port |
| `VECTOR_API_RELOAD=1 python run_api.py` | Auto-restart when you edit code (for developers) |
| `python -m backend.manage list` | List all accounts and their data counts |
| `python -m backend.manage config` | Show every engine setting + safety mode |
| `python -m backend.manage seed-demo` | Create the demo workspace |
| `python -m backend.manage seed-demo --force` | Delete and rebuild the demo workspace |
| `python -m backend.manage create-account --email … --password … --name …` | Create a login |
| `python -m backend.manage run-pipeline --email … --max-leads 3` | Run the live AI engine |
| `python main.py` | Load all agents and print the module tree (a wiring smoke-test) |

From inside `vector-crm/`:

| Command | What it does |
|---|---|
| `npm install` | Install dependencies (first time only) |
| `npm run dev` | Start the dev server on port 5273 |
| `npm run build` | Type-check + build for production into `dist/` |
| `npm run preview` | Serve the built production files |
| `npm run lint` | Type-check only, no build |

**Explore the API directly:** with the backend running, open **http://localhost:8787/docs**. FastAPI generates a live, clickable page listing every endpoint. Click *Authorize*, paste a token from `/api/auth/login`, and try any request in the browser.

---

# 🗺️ How the pieces fit together

```
        YOU (browser at localhost:5273)
                    │
                    ▼
   ┌────────────────────────────────┐
   │  vector-crm  (React frontend)  │   the screen
   │  Dashboard · People · Companies│
   │  Sequences · Analytics         │
   └────────────────────────────────┘
                    │  HTTP + Bearer token
                    ▼
   ┌────────────────────────────────┐
   │  Vector/backend  (FastAPI)     │   the doors
   │  /api/auth  /api/people        │
   │  /api/companies  /api/campaigns│
   └────────────────────────────────┘
          │                    │
          ▼                    ▼
   ┌─────────────┐   ┌──────────────────────┐
   │ SQLite DB   │   │ Vector/modules       │   the brain
   │ data/       │   │  SCOUT  → find leads │
   │ vector.db   │   │  PULSE  → outreach   │
   └─────────────┘   │  CLOSER → close deals│
                     └──────────────────────┘
                                │
                                ▼
                       AI (Claude / Gemini)
```

### The three AI modules

| Module | Job | Sub-parts |
|---|---|---|
| **SCOUT** 🎯 | Find who to sell to | `radar` finds companies + buying signals; `detective` finds decision-makers and their emails |
| **PULSE** 📨 | Reach out | `inbox` writes/sends/A-B-tests email and reads replies; `connect` runs LinkedIn sequences; `scheduling` books meetings |
| **CLOSER** 🤝 | Close | `compass` reads meeting notes and suggests the next best step |

### Folder map

```
VectorOS/
├── README.md                ← you are here
├── .gitignore               ← keeps secrets off GitHub
│
├── Vector/                       BACKEND
│   ├── run_api.py           ← start the API with this
│   ├── main.py              ← agent wiring smoke-test
│   ├── requirements.txt     ← Python dependencies
│   ├── .env.example         ← template for secrets (safe, placeholders only)
│   ├── .env                 ← YOUR secrets (gitignored, you create it)
│   │
│   ├── backend/             ← the web API
│   │   ├── app.py           ← FastAPI app + CORS + startup seeding
│   │   ├── manage.py        ← the command-line tool
│   │   ├── models.py        ← database tables
│   │   ├── security.py      ← password hashing + tokens
│   │   ├── seed.py          ← builds the demo workspace
│   │   ├── orchestrator.py  ← runs the full pipeline end-to-end
│   │   └── routers/         ← one file per API area
│   │
│   ├── modules/             ← the AI engine
│   │   ├── common/          ← config, logging, LLM factory, control panel
│   │   │   └── control.py   ← ⭐ every switch and knob lives here
│   │   ├── scout/           ← radar + detective
│   │   ├── pulse/           ← inbox + connect + scheduling
│   │   └── closer/          ← compass
│   │
│   ├── scripts/             ← manual test scripts per module
│   └── data/                ← SQLite DB + caches (gitignored)
│
└── vector-crm/                   FRONTEND
    ├── package.json         ← npm scripts + dependencies
    ├── vite.config.ts       ← dev server port (5273) + @ alias
    ├── tailwind.config.js   ← design tokens
    ├── DESIGN_SPEC.md       ← the visual source of truth
    └── src/
        ├── main.tsx         ← entry point
        ├── App.tsx          ← routes
        ├── pages/           ← one file per screen
        ├── components/      ← reusable UI
        └── lib/
            ├── api.ts       ← ⭐ every backend call lives here
            ├── auth.tsx     ← login state
            └── types.ts     ← shared TypeScript types
```

---

# ⚙️ Configuration reference

## Changing ports

The frontend defaults to calling `http://localhost:8787`. If you move the backend, tell the frontend where it went by creating `vector-crm/.env.local`:

```env
VITE_API_URL=http://localhost:9000
```

Then restart `npm run dev`. You must **also** let the backend accept the frontend's origin — if you changed the *frontend* port, set `VECTOR_CORS_ORIGINS` in `Vector/.env`:

```env
VECTOR_CORS_ORIGINS=http://localhost:5273,http://localhost:3000
```

> Ports out of the box: backend **8787**, frontend **5273**. The backend already allows `5273`, `5173`, and `127.0.0.1:5273`.

## Backend environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(empty)* | Claude key. Needed only for the live engine. |
| `GOOGLE_API_KEY` | *(empty)* | Gemini key (alternative to Claude). |
| `DEFAULT_LLM_PROVIDER` | `claude` | `claude` or `gemini`. |
| `VECTOR_API_PORT` | `8787` | Backend port. |
| `VECTOR_API_RELOAD` | `0` | `1` = auto-restart on code changes. |
| `VECTOR_CORS_ORIGINS` | `localhost:5273,5173` | Comma-separated origins the API accepts. |
| `VECTOR_SECRET_KEY` | `vector-dev-secret-change-me` | Signs login tokens. **Set a long random value before deploying.** |
| `VECTOR_PULSE_LIVE` | `false` | ⚠️ Master switch for real sending. Keep `false`. |
| `PULSE_AUTO_REPLY` | `false` | Let the AI reply to prospects unattended. |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose output. |

Everything else — Apollo, PDL, Google Search, PhantomBuster, Unipile, Google Calendar, mailbox pools, send windows, warmup caps — is documented inline in `Vector/.env.example`. Read that file; it explains each option and where to get each key.

## Where is my data?

One SQLite file: `Vector/data/vector.db`. It is created and seeded automatically on first boot. It's gitignored, so it stays on your machine. Delete it to wipe everything and start over — it will rebuild on the next start.

---

# 🔒 What is deliberately kept out of Git

These are gitignored and must **never** be committed:

- `Vector/.env` — real API keys and mailbox passwords
- `Vector/data/` — the database, caches, scraped leads
- `client_secret*.json`, `google_token*.json` — Google OAuth credentials
- `.venv/`, `node_modules/` — dependencies (rebuild with `pip install` / `npm install`)
- `vector-crm/dist/`, `__pycache__/`, `.DS_Store` — build output and junk

`Vector/.env.example` **is** committed on purpose — it contains only placeholders like `your-anthropic-api-key`, and it documents what real setup requires.

**If you ever leak a key,** rotate it immediately in the provider's dashboard. Removing it from a file is not enough once it has been pushed — Git keeps history.

---

# 📋 Requirements

| | Minimum | Notes |
|---|---|---|
| **Python** | 3.11+ | Verified on 3.14. Set by `requires-python` in `pyproject.toml`. |
| **Node.js** | 18+ | 20 LTS recommended. |
| **OS** | macOS, Linux, Windows | Windows: use PowerShell and the `.venv\Scripts\Activate.ps1` activate command. |
| **Disk** | ~1 GB | Mostly `node_modules` and `.venv`. |
| **API keys** | none | Only needed for the live engine (Level 2). |

---

# 🧑‍💻 Developer notes

- **Auto-reload while coding:** `VECTOR_API_RELOAD=1 python run_api.py` (backend) — `npm run dev` already hot-reloads the frontend.
- **Adding a new AI module:** create a folder under `Vector/modules/`, add an `agent.py` subclassing `modules.common.base_agent.BaseAgent` with a `run()` method, export it from `__init__.py`, and register it in `main.py`'s `build_engine()`.
- **Adding a new API endpoint:** add a router in `Vector/backend/routers/`, include it in `backend/app.py`, then add the matching typed call to `vector-crm/src/lib/api.ts`.
- **Every switch is centralised.** Don't scatter `os.getenv` calls — add the knob to `modules/common/control.py` and read it from there.
- **All frontend network calls go through `src/lib/api.ts`.** Components never call `fetch` directly, so auth, 401-handling, and error shaping stay in one place.
- **Design changes** should follow `vector-crm/DESIGN_SPEC.md`; tokens live in `tailwind.config.js`.
- **Module test scripts** live in `Vector/scripts/` (`test_apollo.py`, `test_detective.py`, `test_newsradar.py`, …). Run them individually while the venv is active.

---

# ✅ Final checklist

Stuck? Walk this list top to bottom:

- [ ] `python3 --version` shows 3.11 or higher
- [ ] `node --version` shows 18 or higher
- [ ] Terminal 1 is in the `Vector/` folder
- [ ] Terminal 1 shows `(.venv)` in the prompt
- [ ] Terminal 1 says `Uvicorn running on http://0.0.0.0:8787` and is still open
- [ ] http://localhost:8787/api/health returns `{"status":"ok",...}`
- [ ] Terminal 2 is in the `vector-crm/` folder
- [ ] Terminal 2 says `Local: http://localhost:5273/` and is still open
- [ ] Browser is on http://localhost:5273 (not 8787)
- [ ] Logging in with `demo@vector.ai` / `demo1234`

If all ten pass and it still fails, open http://localhost:5273, press `F12`, click **Console**, and read the first red line — it names the real problem.
