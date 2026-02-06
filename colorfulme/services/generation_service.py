from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging

from flask import current_app
from PIL import Image, ImageOps, ImageFilter

from extensions import db
from models import GeneratedAsset, GenerationJob, User
from colorfulme.services.credits_service import InsufficientCreditsError, credit_credits, debit_credits, get_active_plan
from colorfulme.services.moderation_service import ModerationService
from colorfulme.services.openai_client import OpenAIClient
from colorfulme.services.pdf_service import PdfService
from colorfulme.services.storage_service import StorageService
from colorfulme.utils.security import utcnow


CREDIT_COST = {
    'text': 1,
    'photo': 2,
    'recolor': 1,
}

VALID_QUALITY_PROFILES = {'auto', 'economy', 'balanced', 'premium'}


@dataclass(frozen=True)
class RenderPlan:
    profile: str
    model: str
    quality: str


@dataclass
class GenerationResult:
    job: GenerationJob
    asset: GeneratedAsset | None
    credits_used: int
    render_profile: str
    render_model: str
    render_quality: str
    estimated_cost_usd: float | None


class GenerationService:
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.moderation = ModerationService()
        self.storage = StorageService()
        self.pdf = PdfService()

    def create_and_process(
        self,
        *,
        user: User,
        mode: str,
        prompt: str,
        style: str | None,
        aspect_ratio: str | None,
        difficulty: str | None,
        quality_profile: str | None,
        source_image_bytes: bytes | None = None,
    ) -> GenerationResult:
        mode = (mode or 'text').strip().lower()
        if mode not in CREDIT_COST:
            raise ValueError('Invalid generation mode')

        prompt = (prompt or '').strip()
        if len(prompt) > 400:
            raise ValueError('Prompt exceeds 400 characters')

        if mode in {'text', 'recolor'} and not prompt:
            raise ValueError('Prompt is required for this generation mode')

        if mode == 'photo' and source_image_bytes is None:
            raise ValueError('Source image is required for photo mode')

        plan = get_active_plan(user)
        render_plan = self._resolve_render_plan(
            requested_profile=quality_profile,
            difficulty=difficulty,
            plan_code=plan.code if plan else 'free',
        )

        job = GenerationJob(
            user_id=user.id,
            mode=mode,
            prompt=prompt,
            style=(style or '').strip()[:80] or None,
            aspect_ratio=(aspect_ratio or '1:1').strip()[:20],
            difficulty=(difficulty or '').strip()[:40] or None,
            status='queued',
            cost_credits=CREDIT_COST[mode],
        )
        db.session.add(job)
        db.session.commit()

        allowed, reason = self.moderation.check_prompt(prompt or 'family-safe coloring page')
        if not allowed:
            job.status = 'blocked'
            job.error_message = reason
            job.completed_at = utcnow()
            db.session.commit()
            return GenerationResult(
                job=job,
                asset=None,
                credits_used=0,
                render_profile=render_plan.profile,
                render_model=render_plan.model,
                render_quality=render_plan.quality,
                estimated_cost_usd=None,
            )

        try:
            debit_credits(user, job.cost_credits, reason='generation', reference_id=job.id)
        except InsufficientCreditsError as exc:
            job.status = 'failed'
            job.error_message = str(exc)
            job.completed_at = utcnow()
            db.session.commit()
            return GenerationResult(
                job=job,
                asset=None,
                credits_used=0,
                render_profile=render_plan.profile,
                render_model=render_plan.model,
                render_quality=render_plan.quality,
                estimated_cost_usd=None,
            )

        job.status = 'processing'
        db.session.commit()

        try:
            render = self.openai_client.generate_image(
                prompt=prompt or 'Printable coloring page',
                mode=mode,
                style=style,
                aspect_ratio=aspect_ratio,
                source_image=source_image_bytes,
                model=render_plan.model,
                quality=render_plan.quality,
            )
            clean_png = self._post_process_line_art(render.png_bytes)
            pdf_bytes = self.pdf.png_to_pdf_bytes(clean_png)

            png_key, png_url = self.storage.save_bytes(clean_png, extension='png', folder=f'{user.id}/{job.id}')
            pdf_key, pdf_url = self.storage.save_bytes(pdf_bytes, extension='pdf', folder=f'{user.id}/{job.id}')

            width, height = self._image_dimensions(clean_png)

            asset = GeneratedAsset(
                user_id=user.id,
                job_id=job.id,
                png_key=png_key,
                pdf_key=pdf_key,
                png_url=png_url,
                pdf_url=pdf_url,
                width=width,
                height=height,
            )
            db.session.add(asset)

            job.status = 'completed'
            job.completed_at = utcnow()
            db.session.commit()
            return GenerationResult(
                job=job,
                asset=asset,
                credits_used=job.cost_credits,
                render_profile=render_plan.profile,
                render_model=render.model,
                render_quality=render.quality,
                estimated_cost_usd=render.estimated_cost_usd,
            )

        except Exception as exc:
            logging.exception('Generation failed for job=%s', job.id)
            credit_credits(user, job.cost_credits, reason='generation_refund', reference_id=job.id)
            job.status = 'failed'
            job.error_message = str(exc)
            job.completed_at = utcnow()
            db.session.commit()
            return GenerationResult(
                job=job,
                asset=None,
                credits_used=0,
                render_profile=render_plan.profile,
                render_model=render_plan.model,
                render_quality=render_plan.quality,
                estimated_cost_usd=None,
            )

    @staticmethod
    def _normalize_profile(value: str | None) -> str:
        cleaned = (value or '').strip().lower()
        if cleaned in VALID_QUALITY_PROFILES:
            return cleaned
        return 'auto'

    def _resolve_render_plan(self, *, requested_profile: str | None, difficulty: str | None, plan_code: str) -> RenderPlan:
        profile = self._normalize_profile(requested_profile)
        difficulty = (difficulty or '').strip().lower()
        plan_code = (plan_code or 'free').strip().lower()

        if profile == 'auto':
            if plan_code in {'pro', 'studio', 'lifetime'} and difficulty == 'detailed':
                profile = 'premium'
            elif plan_code in {'pro', 'studio', 'lifetime'}:
                profile = 'balanced'
            else:
                profile = 'economy'

        model = {
            'economy': current_app.config.get('OPENAI_MODEL_ECONOMY', 'gpt-image-1.5'),
            'balanced': current_app.config.get('OPENAI_MODEL_BALANCED', 'gpt-image-1.5'),
            'premium': current_app.config.get('OPENAI_MODEL_PREMIUM', 'gpt-image-1.5'),
        }[profile]
        quality = {
            'economy': current_app.config.get('OPENAI_QUALITY_ECONOMY', 'low'),
            'balanced': current_app.config.get('OPENAI_QUALITY_BALANCED', 'medium'),
            'premium': current_app.config.get('OPENAI_QUALITY_PREMIUM', 'high'),
        }[profile]

        return RenderPlan(profile=profile, model=(model or 'gpt-image-1.5').strip(), quality=(quality or 'medium').strip().lower())

    @staticmethod
    def _post_process_line_art(png_bytes: bytes) -> bytes:
        image = Image.open(BytesIO(png_bytes)).convert('L')
        image = ImageOps.autocontrast(image)
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Normalize to white background + black outlines only.
        image = image.point(lambda p: 255 if p > 170 else 0)
        rgb = image.convert('RGB')
        out = BytesIO()
        rgb.save(out, format='PNG', optimize=True)
        return out.getvalue()

    @staticmethod
    def _image_dimensions(png_bytes: bytes) -> tuple[int, int]:
        image = Image.open(BytesIO(png_bytes))
        return image.width, image.height
