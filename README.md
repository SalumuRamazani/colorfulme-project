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
5. Open:
   - `http://127.0.0.1:5003/`

## Programmatic SEO Workflow
- Edit `content/programmatic_content.csv`
- Generate manifest:
  ```bash
  ./scripts/run_programmatic_pipeline.sh
  ```
- Only rows with `status=published` are routed live.
- Registry endpoint: `/programmatic/content`

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
