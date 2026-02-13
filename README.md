# ColorfulMe V1

ColorfulMe is a Flask-based AI coloring page platform that generates printable line-art from text prompts and photos.

## What This Build Includes
- Hard pivot from receipt SaaS to coloring-page product.
- Blue-first responsive landing and app UI.
- Generation modes: `text`, `photo`, `recolor`.
- Strict family-safe moderation.
- PNG + PDF export.
- Freemium credits + Stripe paid plans (`starter`, `pro`, `studio`, `lifetime`).
- Google OAuth + Email OTP auth.
- S3-compatible storage with local fallback.
- Programmatic SEO pipeline from a single spreadsheet (`page|tool|library`, review gating).
- Public API keys + usage logging + rate limiting.

## Tech
- Flask + SQLAlchemy + Flask-Login
- Pillow (image processing)
- Stripe
- OpenAI image generation (with local fallback in development)
- Tailwind CSS for styling

## Quality + Margin Optimizer
- `quality_profile` supports `auto`, `economy`, `balanced`, `premium`.
- `auto` is plan-aware:
  - `free` / `starter` defaults to `economy` for better margins.
  - `pro` / `studio` / `lifetime` defaults to `balanced`.
  - `detailed` jobs on paid plans can auto-upgrade to `premium`.
- Per-profile model + quality are configurable via env vars (`OPENAI_MODEL_*`, `OPENAI_QUALITY_*`).
- Generation responses now include selected render settings and estimated per-image model cost when available.

## Quick Start
1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   ```
3. Generate programmatic manifest:
   ```bash
   python3 scripts/generate_programmatic_content.py
   ```
4. Run the app:
   ```bash
   python3 app.py
   ```
   For local development with no login required:
   ```bash
   LOCAL_DEV_AUTO_LOGIN=true LOCAL_DEV_UNLIMITED_CREDITS=true python3 app.py
   ```
   Or use:
   ```bash
   ./run_dev.sh
   ```
5. Open:
   - `http://127.0.0.1:5003/`

## Local No-Login Dev Mode
- `LOCAL_DEV_AUTO_LOGIN=true` auto-authenticates a deterministic local user on every request.
- `LOCAL_DEV_UNLIMITED_CREDITS=true` disables credit debit for that local dev user.
- Optional identity overrides:
  - `LOCAL_DEV_AUTO_LOGIN_EMAIL=local-dev@colorfulme.app`
  - `LOCAL_DEV_AUTO_LOGIN_NAME=Local Dev`
- Safety guard: local auto-login is rejected unless `DEBUG=true` or `TESTING=true`.

## Programmatic SEO Workflow
- Edit `content/programmatic_content.csv`
- Generate manifest only:
  ```bash
  ./scripts/run_programmatic_pipeline.sh
  ```
- Fill content + hero drawings at scale (review-gated):
  ```bash
  python3 scripts/fill_programmatic_content_and_images.py --mode all --batch-id batch-YYYYMMDDHHMM
  ```
- Validate readiness:
  ```bash
  python3 scripts/validate_programmatic_readiness.py
  ```
- One-command fill + validate:
  ```bash
  ./scripts/run_programmatic_live_pipeline.sh
  ```
- Publish approved review rows only:
  ```bash
  python3 scripts/publish_programmatic_batch.py --batch-id batch-YYYYMMDDHHMM
  ```
- Only rows with `status=published` are routed live.
- Registry endpoint: `/programmatic/content`

### Programmatic Pipeline Columns
Optional operational columns are supported in the spreadsheet and preserved in the manifest:
- `content_status` (`pending|generated|approved`)
- `image_status` (`pending|generated|approved|failed`)
- `primary_keyword`
- `secondary_keywords` (`|` separated)
- `content_brief`
- `image_style`
- `image_aspect_ratio`
- `image_prompt_override`
- `asset_local_path`
- `asset_hash`
- `generation_batch_id`
- `last_generated_at`
- `last_reviewed_at`
- `qa_notes`

## Readable Programmatic Content
- Programmatic category and entry pages now render through a presenter view-model to avoid dense text blocks.
- Content is split into structured sections:
  - `Overview`
  - `How To Use This Page`
  - `Practical Tips`
- Readability defaults:
  - Body copy targets at least 3 paragraphs.
  - Keep paragraph length compact (recommended max around 120 words each).
  - Preserve family-safe language and practical usage guidance.

### Refresh Readability Copy (Targeted)
Run a content-only refresh for free coloring pages into a named batch:
```bash
python3 scripts/fill_programmatic_content_and_images.py \
  --mode content \
  --filter entry_type=page \
  --batch-id readability-YYYYMMDDHHMM \
  --force-content
```

Validate readability and publish readiness:
```bash
python3 scripts/validate_programmatic_readiness.py
```

## API Endpoints
- `POST /api/v1/generations/text`
- `POST /api/v1/generations/photo`
- `POST /api/v1/generations/recolor`
- `GET /api/v1/jobs/<job_id>`
- `GET /api/v1/assets/<asset_id>/download?format=png|pdf`
- `GET /api/v1/me/credits`
- `POST /api/v1/developer/keys`
- `GET /api/v1/developer/keys`
- `DELETE /api/v1/developer/keys/<key_id>`

### Generation Payload
- Common request fields:
  - `prompt`
  - `style`
  - `aspect_ratio`
  - `difficulty`
  - `quality_profile` (`auto|economy|balanced|premium`)
  - `source_image_base64` (for photo/recolor)

## Auth Routes
- `GET /auth/google/start`
- `GET /auth/google/callback`
- `POST /auth/email/send-code`
- `POST /auth/email/verify-code`
- `POST /auth/logout`

## Notes
- Old receipt files/assets remain in the repository but are no longer reachable from runtime routes.
- Legacy DB was archived to `instance/receiptforge.db.bak-20260206`.
