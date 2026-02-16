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

<!-- TASKMASTER_EXPORT_START -->
> 🎯 **Taskmaster Export** - 2026-02-16 10:16:30 UTC
> 📋 Export: with subtasks • Status filter: none
> 🔗 Powered by [Task Master](https://task-master.dev?utm_source=github-readme&utm_medium=readme-export&utm_campaign=colorfulme-project&utm_content=task-export-link)

```
╭─────────────────────────────────────────────────────────╮╭─────────────────────────────────────────────────────────╮
│                                                         ││                                                         │
│   Project Dashboard                                     ││   Dependency Status & Next Task                         │
│   Tasks Progress: ███████░░░░░░░░░░░░░ 33%    ││   Dependency Metrics:                                   │
│   33%                                                   ││   • Tasks with no dependencies: 0                      │
│   Done: 4  In Progress: 5  Pending: 3  Blocked: 0     ││   • Tasks ready to work on: 2                          │
│   Deferred: 0  Cancelled: 0                             ││   • Tasks blocked by dependencies: 6                    │
│                                                         ││   • Most depended-on task: #3 (4 dependents)           │
│   Subtasks Progress: █████████████░░░░░░░     ││   • Avg dependencies per task: 1.8                      │
│   67% 67%                                               ││                                                         │
│   Completed: 8/12  In Progress: 2  Pending: 2      ││   Next Task to Work On:                                 │
│   Blocked: 0  Deferred: 0  Cancelled: 0                 ││   ID: 11.1 - Desktop QA matrix     │
│                                                         ││   Priority: high  Dependencies: None                    │
│   Priority Breakdown:                                   ││   Complexity: N/A                                       │
│   • High priority: 9                                   │╰─────────────────────────────────────────────────────────╯
│   • Medium priority: 3                                 │
│   • Low priority: 0                                     │
│                                                         │
╰─────────────────────────────────────────────────────────╯
┌───────────┬──────────────────────────────────────┬─────────────────┬──────────────┬───────────────────────┬───────────┐
│ ID        │ Title                                │ Status          │ Priority     │ Dependencies          │ Complexi… │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 1         │ Global Navigation & Header Polish    │ ✓ done          │ high         │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 1.1       │ └─ Desktop dropdown usability        │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 1.2       │ └─ Mobile menu hierarchy             │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 2         │ Create Flow UX Finish                │ ✓ done          │ high         │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 2.1       │ └─ Generation status messaging       │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 2.2       │ └─ Form validation polish            │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 3         │ Free Category Page Polish            │ ✓ done          │ high         │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 3.1       │ └─ Readability spacing audit         │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 3.2       │ └─ Sidebar behavior                  │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 4         │ Generic Programmatic Entry Polish    │ ✓ done          │ high         │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 4.1       │ └─ Hero-media composition            │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 4.2       │ └─ FAQ disclosure polish             │ ✓ done          │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 5         │ Image & Asset Consistency Audit      │ ○ pending       │ high         │ 3, 4                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 6         │ Landing Page Visual Consistency Swee │ ► in-progress   │ medium       │ 1                     │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 7         │ Accessibility Hardening              │ ► in-progress   │ high         │ 1, 2, 3, 4, 6         │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 8         │ SEO Metadata & Structured Data Harde │ ► in-progress   │ medium       │ 3, 4, 6               │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 9         │ Performance Pass                     │ ○ pending       │ medium       │ 5, 6                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 10        │ Error, Empty, and Edge-State Coverag │ ► in-progress   │ high         │ 2, 3, 4, 5            │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 11        │ Cross-Device QA & Bug Bash           │ ► in-progress   │ high         │ 7, 8, 9, 10           │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 11.1       │ └─ Desktop QA matrix                 │ ► in-progress   │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 11.2       │ └─ Mobile QA matrix                  │ ► in-progress   │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 12        │ Release Readiness & Go-Live Runbook  │ ○ pending       │ high         │ 11                    │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 12.1       │ └─ Go-live checklist                 │ ○ pending       │ -            │ None                  │ N/A       │
├───────────┼──────────────────────────────────────┼─────────────────┼──────────────┼───────────────────────┼───────────┤
│ 12.2       │ └─ Post-launch watch                 │ ○ pending       │ -            │ None                  │ N/A       │
└───────────┴──────────────────────────────────────┴─────────────────┴──────────────┴───────────────────────┴───────────┘
```

╭────────────────────────────────────────────── ⚡ RECOMMENDED NEXT TASK ⚡ ──────────────────────────────────────────────╮
│                                                                                                                         │
│  🔥 Next Task to Work On: #11.1 - Desktop QA matrix                                  │
│                                                                                                                         │
│  Priority: high   Status: ► in-progress                                                                                     │
│  Dependencies: None                                                                                                     │
│                                                                                                                         │
│  Description: Run and log desktop checks on primary routes.     │
│                                                                                                                         │
│  Start working: task-master set-status --id=11.1 --status=in-progress                                                     │
│  View details: task-master show 11.1                                                                      │
│                                                                                                                         │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


╭──────────────────────────────────────────────────────────────────────────────────────╮
│                                                                                      │
│   Suggested Next Steps:                                                              │
│                                                                                      │
│   1. Run task-master next to see what to work on next                                │
│   2. Run task-master expand --id=<id> to break down a task into subtasks             │
│   3. Run task-master set-status --id=<id> --status=done to mark a task as complete   │
│                                                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────╯

> 📋 **End of Taskmaster Export** - Tasks are synced from your project using the `sync-readme` command.
<!-- TASKMASTER_EXPORT_END -->

