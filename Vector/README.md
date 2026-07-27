# Vector

**Vector** is a multi-modular, agent-powered **GTM (Go-To-Market) Engine**.
Each capability of the go-to-market motion is an independent module driven by an
LLM agent, sharing a common core for configuration, logging, LLM access, and tools.

## Project structure

```
Vector/
├── main.py                  # Entry point — wires the modules together
├── requirements.txt         # Dependencies
├── pyproject.toml           # Project metadata & build config
├── .env.example             # Template for environment variables
├── .gitignore
│
├── modules/                 # GTM modules (each is an agent-powered capability)
│   ├── common/              # Shared core used by every module
│   │   ├── config.py        # Env-based settings (dotenv)
│   │   ├── logger.py        # Shared logging setup
│   │   ├── llm.py           # LLM factory (Claude + Gemini via LangChain)
│   │   ├── base_agent.py    # BaseAgent all module agents inherit
│   │   └── tools/           # Reusable tools agents can call
│   │       └── base_tool.py # BaseTool all tools inherit
│   │
│   ├── scout/               # 🎯 Lead Generation
│   │   ├── radar/           # Finds companies & leads across sources
│   │   └── detective/       # Uncovers decision-makers + contact data
│   ├── pulse/               # 📨 Outreach
│   │   ├── inbox/           # Personalized emails, sequences, sends
│   │   └── connect/         # LinkedIn sequences for decision-makers
│   └── closer/              # 🤝 Deal Closing
│       └── compass/         # Analyzes meeting notes → next best step
│
└── data/                    # Local data (gitignored, kept empty)
```

> Module names are placeholders and will evolve as the engine matures.

## Setup

```bash
# 1. Create & activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# then edit .env and add your API keys

# 4. Run
python main.py
```

## LLM providers

Vector supports two providers out of the box, both through LangChain:

- **Claude** (Anthropic) — set `ANTHROPIC_API_KEY`
- **Gemini** (Google) — set `GOOGLE_API_KEY`

Choose the default with `DEFAULT_LLM_PROVIDER` in `.env` (`claude` or `gemini`).

## Adding a module

1. Create a folder under `modules/`.
2. Add an `agent.py` with a class that subclasses
   `modules.common.base_agent.BaseAgent` and implements `run()`.
3. Export it from the module's `__init__.py`.
4. Register it in `main.py`'s `build_engine()`.
```
