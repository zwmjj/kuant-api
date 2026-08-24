# kuant-api

FastAPI backend for the **Kuant quantitative research platform**.
Serves a 20-router REST surface covering backtesting, factor research,
strategy runs, risk analytics, audit reports, and an in-browser
code IDE for custom strategies.

## Ecosystem

This is one of **six open-source repositories** that together form a
complete quant research platform. Total ~55,000 LOC, MIT licensed.

| Repo | Role | LOC |
|---|---|---|
| [`alt-data-research`](https://github.com/zwmjj/alt-data-research) | SEC NLP + 13F alt-data alpha — combined ICIR 0.80 in-sample; component signs fitted on the same sample, so the t-stat is not a significance test | ~2.5k |
| [`kuant-research`](https://github.com/zwmjj/kuant-research) | 14 reproducible empirical studies with committed expected outputs | ~3k |
| [`kuant-core`](https://github.com/zwmjj/kuant-core) | Production quant research library — 28+ factors, walk-forward CV, 5 cost models, US + CN A-share | ~20k |
| [`kuant-strategies`](https://github.com/zwmjj/kuant-strategies) | 25+ strategies built on kuant-core: momentum, mean-rev, crypto, options, ML, alt-data | ~17k |
| **`kuant-api`** (this repo) | FastAPI research backend — 20 routers, Monaco IDE, WebSocket, JWT auth | ~5k |
| [`kuant-web`](https://github.com/zwmjj/kuant-web) | Next.js 16 + Tailwind + Recharts dashboard — 20 panels | ~7k |

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

- Bearer tokens signed with HMAC-SHA256 using `KUANT_API_SECRET_KEY` from
  env. Note these are **not** JWTs, despite what this section used to say —
  the format is `base64(payload|hmac)`, not the RFC 7519 three-part form.
- User store is `KUANT_API_USERS` env var: comma-separated
  `username:sha256_hash` pairs
- **Both variables are required.** The server raises at import if either is
  unset, unless `KUANT_API_ALLOW_INSECURE_DEV=1` is set explicitly.

  This section previously said a `demo/demo` fallback loads "ONLY when
  `KUANT_API_USERS` is empty, and a warning is printed". The first half was
  true and the second was not: no warning was printed, and the same silent
  fallback applied to the signing key. An instance deployed without those
  env vars signed its tokens with a string committed to this public
  repository, so anyone reading the source could forge a valid token for any
  username. The fallbacks still exist for local development but no longer
  engage by accident.
- Passwords are compared as bare unsalted SHA-256, which is weak for a
  password store. Changing it would invalidate every account configured
  through `KUANT_API_USERS`, so it is documented rather than silently
  changed; argon2id or bcrypt with a per-user salt is the correct fix and
  belongs in its own change.

## Secrets policy

This repo **never** contains:
- API keys, or any credential for an external service

It did, until 2026-08-24, contain a development signing key and a
`demo/demo` account as silent fallbacks in `api/config.py`. Neither was a
secret in any useful sense once committed here, which is exactly the
problem — they are still present as opt-in development conveniences, gated
behind `KUANT_API_ALLOW_INSECURE_DEV=1`, and the server refuses to start on
them otherwise. Treat both as public.

Also never in this repo:
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
