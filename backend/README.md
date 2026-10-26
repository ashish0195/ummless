# Comlogue API

Backend for **Comlogue**, an AI communication coach. It runs the guided AI-roleplay assessment, analyzes uploaded
and live-recorded conversations, builds an **evidence-based, partial-when-necessary** communication profile, and
powers the course, missions, sparring, talks and weekly review.

- Contract: [`../docs/API.md`](../docs/API.md) (generated OpenAPI: [`../docs/openapi.json`](../docs/openapi.json))
- Product rules: [`../docs/PRODUCT_DECISIONS.md`](../docs/PRODUCT_DECISIONS.md) and the spec in [`../docs/spec`](../docs/spec)

## Quick start (no API key needed)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Without `OPENAI_API_KEY` the server runs in **demo mode** (`AI_PROVIDER=auto` → offline provider): every response
carries `demo_mode: true` and the app shows a "Demo" badge. Demo mode cannot hear audio, so transcripts are
illustrative, but the real pipeline still runs on your audio: quality gates, speaker separation, evidence caps,
partial profiles and "Not enough evidence yet".

To fill an account with realistic data for design QA, call `POST /v1/dev/seed-demo {"pro": true}`.

## Real AI

```bash
cp .env.example .env     # then set OPENAI_API_KEY=sk-...
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

| Job | Default model chain (first available wins, then remembered) |
| --- | --- |
| Evidence assessment, attempt feedback, spar reports, debriefs | `gpt-6.1-sol` → `gpt-6-sol` → `gpt-5.5` (reasoning: medium) |
| Partner replies, coach whispers, reflections, event prep | `gpt-6-luna` → `gpt-5.4-mini` → `gpt-5-mini` (reasoning: low) |
| Turn transcription (with token log-probs for intelligibility) | `gpt-4o-transcribe` → `gpt-4o-mini-transcribe` |
| Diarization + known-speaker (voice reference) matching | `gpt-4o-transcribe-diarize` |
| Partner voices | `gpt-4o-mini-tts` (voices `marin`, `cedar`, `coral`, …) — app falls back to on-device speech |

All lists are configurable (`ASSESSMENT_MODELS=…`, comma-separated). Calls use the SDK's retries for 429/5xx, a
model-fallback chain for "model not found / no access", and `store=False`. If transcription fails, the turn
endpoint returns `503 ai_unavailable` and nothing is lost. If a partner reply fails, a scripted line is used.

**Rough cost per user** (check current OpenAI pricing): a 10–15 minute guided assessment is about $0.15–$0.30
(transcription + background-voice check ≈ $0.06, partner lines + TTS ≈ $0.03, evidence assessment ≈ $0.06–$0.16).
A 30-minute uploaded meeting is about $0.30–$0.45.

## How an analysis works

```
audio ─▶ decode (ffmpeg, 16 kHz mono) ─▶ usability check (10 s windows: level, noise, clipping, speech)
      ─▶ who is speaking?  roleplay: isolated mic + diarization to drop background voices
                          recordings: diarization with the consented voice reference as a known speaker,
                                      + local MFCC/pitch conflict check ─▶ confirmation (always on the first
                                      conversation, without a reference, or when weak/conflicting)
      ─▶ evidence per dimension: deterministic opportunity caps (e.g. listening needs ≥2 substantive exchanges)
                                 ∩ model judgement against a rubric that must cite moments
      ─▶ result: complete / partial / none + the smallest follow-up; evidence clips; no overall score
```

Server-side guards always win over the model: no opportunity or too little attributed speech ⇒ "Not enough
evidence yet" with `level: null`; an uncited claim is dropped; low transcription confidence ⇒ the turn is
excluded (never scored); accents are never scored. All thresholds are in `app/domain/evidence.py`,
`app/audio/quality.py` and `app/audio/voiceprint.py` and are marked **pilot calibration required**.

## Layout

```
app/
  main.py            app factory (+ lazy `app` for `uvicorn app.main:app`), job recovery on startup
  config.py          settings (env / .env)          schemas.py   API models (mirror docs/API.md)
  models.py          SQLAlchemy tables               errors.py    error envelope
  ai/                provider interface, OpenAI provider, offline demo provider, prompts, structured-output schemas
  audio/             ffmpeg helpers, quality checks, voiceprint conflict check, speech statistics
  domain/            dimensions + rubrics, evidence rules, activities (Maya), course content, personas, talks,
                     recording rules by region, consent texts, style archetypes
  services/          conversations (turn engine), assessments, recordings, analysis, profile, course & missions,
                     spar, events, talks, review, progress, billing, voice reference, feedback, demo seed, account
  routers/           HTTP endpoints
scripts/             export_openapi.py · export_contract_fixtures.py · build_twin_profile.py · pilot_metrics.py
tests/               pytest suite (synthetic speech generated with numpy + ffmpeg)
```

## Tests, lint, contract artifacts

```bash
pip install -r requirements.txt
ruff check app tests scripts
pytest                                   # uses the offline provider and synthetic audio
python scripts/export_openapi.py         # → ../docs/openapi.json
python scripts/export_contract_fixtures.py   # → ../contract-fixtures/*.json (decoded by the Swift tests)
```

Every JSON response in the test suite is checked for the contract rules: no overall score, timestamps without
fractional seconds, and missing evidence never carrying a level or confidence.

## Pilot metrics

```bash
python scripts/pilot_metrics.py --since 2026-11-01   # reads DATABASE_URL
```

Prints the spec's pilot measures for everyone who joined since that date: first-task completion, voluntary
retries, return for the next mission and real-life application (engagement), improvement on a fresh scenario
(learning), and "Not quite right?" reports by reason (calibration). Seeded demo accounts are left out.

## Deploy

**Docker:** `docker build -t comlogue-api . && docker run -p 8000:8000 --env-file .env -v comlogue:/data comlogue-api`
(SQLite and media under `/data`). `docker compose up --build` runs the API with Postgres.

**Render / Fly.io / Railway:** deploy the Dockerfile, set `OPENAI_API_KEY`, `SECRET_KEY` (32+ random characters; production refuses placeholders), `ENVIRONMENT=production`,
attach a persistent volume at `/data` (or set `DATABASE_URL` to managed Postgres:
`postgresql+psycopg://…`). Health check: `GET /v1/health`. Point the iOS app's `API_BASE_URL` at the service.

## Before launch (known gaps)

- **App Store purchases are not cryptographically verified yet** (`services/billing.py`): implement Apple JWS
  verification (app-store-server-library), then set `APP_STORE_REQUIRE_VERIFICATION=true`.
- Schema migrations: tables are created with `create_all`; add Alembic before the first schema change in production.
- Single-process pieces: background jobs (thread pool, restart-safe via DB state) and the rate limiter are
  in-process. For several instances, move jobs to a queue (RQ/Celery/Arq) and rate limits to Redis.
- Media is on local disk (`storage.py` is a small interface ready for S3/GCS).
- Legal review: voice references may be biometric identifiers (BIPA/CUBI/WA); recording-consent text by region
  is general information. See `docs/PRODUCT_DECISIONS.md` §6–7.
- Calibrate quality, speaker-match and evidence thresholds in the pilot (noise, overlap, short turns, microphones,
  languages, accents).
