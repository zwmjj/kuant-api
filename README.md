# kuant-api

FastAPI backend for the **Kuant quantitative research platform**.
Serves a 20-router REST surface covering backtesting, factor research,
strategy runs, risk analytics, audit reports, and an in-browser
code IDE for custom strategies.

> Companion repos:
> [`kuant-core`](https://github.com/zwmjj/kuant-core) — research library.
> [`kuant-strategies`](https://github.com/zwmjj/kuant-strategies) — 25+ strategies.
> [`kuant-web`](https://github.com/zwmjj/kuant-web) — Next.js frontend.

## Routers (20)

| Path | Role |
|---|---|
| `/auth`         | JWT login + user management (env-var backed user store) |
| `/dashboard`    | Home page summary stats |
| `/backtest`     | POST /run — configurable backtest (US + CN routing) |
| `/factors`      | Factor library listing, IC/ICIR, correlation matrix |
| `/factor_lab`   | Interactive factor construction / blend UI backend |
| `/strategies`   | Strategy catalogue + per-strategy details |
| `/research`     | 14 research studies with chart data |
| `/audit`        | Phase 3+4 SOP audit results |
| `/sop`          | Strategy-of-production gate checks |
| `/advanced`     | Advanced analytics (stress, regime, attribution) |
| `/risk`         | VaR / CVaR / drawdown / tail risk |
| `/code`         | IDE code-execution sandbox (Monaco-editor backend) |
| `/agents`       | Multi-agent system control panel |
| `/credits`      | Usage / credit tracking |
| `/downloads`    | Artifact download (reports, CSVs, pickles) |
| `/websocket`    | Real-time data push for monitor / stream pages |

All routers are mounted by `api/main.py` with CORS, lifespan startup,
and dependency injection for the research library (`qf.*`) +
optional live data feeds (Alpaca / WRDS).

## Quickstart

```bash
git clone https://github.com/zwmjj/kuant-api
cd kuant-api
pip install -r requirements.txt
pip install git+https://github.com/zwmjj/kuant-core.git  # or pip install kuant-core when on pypi

cp .env.example .env
# edit .env with real secrets (see .env.example for what's needed)

uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
# → http://127.0.0.1:8000/docs  (OpenAPI / Swagger UI)
# → http://127.0.0.1:8000/redoc (ReDoc)
```

## Authentication

- JWT tokens signed with `KUANT_API_SECRET_KEY` from env
- User store is `KUANT_API_USERS` env var: comma-separated
  `username:sha256_hash` pairs
- No users are hardcoded — a dev fallback `demo/demo` user loads
  ONLY when `KUANT_API_USERS` is empty, and a warning is printed

## Secrets policy

This repo **never** contains:
- API keys / secret keys / JWT signing keys
- User passwords (hashed or plaintext)
- WRDS / Alpaca / Bloomberg credentials
- Database connection strings with credentials
- Any `.env` file

All of the above are loaded from env vars at runtime via
`os.environ.get()`. See `api/config.py` and `.env.example` for the
expected variable names. In production, inject via your platform's
secret manager (K8s Secrets, AWS Parameter Store, HashiCorp Vault,
GitHub Actions secrets, etc).

## Project layout

```
kuant-api/
├── api/
│   ├── main.py              # FastAPI app init, CORS, lifespan
│   ├── config.py            # env-var loaders for SECRET_KEY + USERS
│   ├── routers/             # 20 router modules
│   ├── schemas/             # Pydantic request/response models
│   └── services/            # business logic (backtest_service, etc)
├── requirements.txt
├── .env.example
├── README.md
└── LICENSE
```

## License

MIT. See `LICENSE`.
