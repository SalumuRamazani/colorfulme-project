from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import logging
from urllib.request import urlopen

from flask import current_app
from PIL import Image, ImageDraw, ImageFilter, ImageOps


_IMAGE_PRICE_USD = {
    'gpt-image-1.5': {
        'low': {'1024x1024': 0.009, '1024x1536': 0.013, '1536x1024': 0.013},
        'medium': {'1024x1024': 0.034, '1024x1536': 0.050, '1536x1024': 0.050},
        'high': {'1024x1024': 0.133, '1024x1536': 0.200, '1536x1024': 0.200},
    },
    'gpt-image-1': {
        'low': {'1024x1024': 0.011, '1024x1536': 0.016, '1536x1024': 0.016},
        'medium': {'1024x1024': 0.042, '1024x1536': 0.063, '1536x1024': 0.063},
        'high': {'1024x1024': 0.167, '1024x1536': 0.250, '1536x1024': 0.250},
    },
    'gpt-image-1-mini': {
        'low': {'1024x1024': 0.005, '1024x1536': 0.006, '1536x1024': 0.006},
        'medium': {'1024x1024': 0.011, '1024x1536': 0.015, '1536x1024': 0.015},
        'high': {'1024x1024': 0.036, '1024x1536': 0.052, '1536x1024': 0.052},
    },
}


@dataclass(frozen=True)
class GeneratedImage:
    png_bytes: bytes
    model: str
    quality: str
    size: str
    estimated_cost_usd: float | None
    used_fallback: bool = False


class OpenAIClient:
    def __init__(self):
        self.api_key = (current_app.config.get('OPENAI_API_KEY') or '').strip()
        self.model = current_app.config.get('OPENAI_MODEL', 'gpt-image-1.5')
        self.fallback_model = current_app.config.get('OPENAI_MODEL_FALLBACK', 'gpt-image-1-mini')
        self.default_quality = current_app.config.get('OPENAI_IMAGE_QUALITY_DEFAULT', 'medium')
        self.allow_fake = bool(current_app.config.get('ALLOW_FAKE_AI', True))

    def generate_image(
        self,
        *,
        prompt: str,
        mode: str,
        style: str | None = None,
        aspect_ratio: str | None = None,
        source_image: bytes | None = None,
        model: str | None = None,
        quality: str | None = None,
    ) -> GeneratedImage:
        model = (model or self.model).strip()
        quality = self._normalize_quality(quality or self.default_quality)
        size = self._aspect_ratio_to_size(aspect_ratio)

        if self.api_key:
            candidates = self._candidate_models(model)
            last_error: Exception | None = None
            for candidate in candidates:
                try:
                    image_bytes = self._generate_openai_image(
                        prompt=prompt,
                        mode=mode,
                        style=style,
                        model=candidate,
                        quality=quality,
                        size=size,
                    )
                    return GeneratedImage(
                        png_bytes=image_bytes,
                        model=candidate,
                        quality=quality,
                        size=size,
                        estimated_cost_usd=self.estimate_image_cost_usd(candidate, quality, size),
                    )
                except Exception as exc:
                    last_error = exc
                    logging.warning('OpenAI generation failed for model=%s: %s', candidate, exc)
            if not self.allow_fake and last_error is not None:
                raise last_error

        if not self.allow_fake:
            raise RuntimeError('OpenAI API key is missing and ALLOW_FAKE_AI is disabled')
        image_bytes = self._generate_fallback_image(
            prompt=prompt,
            mode=mode,
            style=style,
            aspect_ratio=aspect_ratio,
            source_image=source_image,
        )
        return GeneratedImage(
            png_bytes=image_bytes,
            model='fallback-deterministic',
            quality='n/a',
            size=size,
            estimated_cost_usd=None,
            used_fallback=True,
        )

    def _generate_openai_image(
        self,
        *,
        prompt: str,
        mode: str,
        style: str | None,
        model: str,
        quality: str,
        size: str,
    ) -> bytes:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        style_label = (style or 'clean line art').strip()
        system_prompt = (
            'Create a black-and-white printable coloring page. '
            'No grayscale fills. Use clear, closed outlines and large colorable regions for kids. '
            'Family-safe content only. White background.'
        )

        user_prompt = f"Mode: {mode}. Style: {style_label}. Request: {prompt}" if style_label else prompt

        response = client.images.generate(
            model=model,
            prompt=f"{system_prompt}\n\n{user_prompt}",
            size=size,
            quality=quality,
            response_format='b64_json',
        )

        data = response.data[0]
        b64_json = getattr(data, 'b64_json', None)
        if b64_json:
            return base64.b64decode(b64_json)

        url = getattr(data, 'url', None)
        if url:
            with urlopen(url) as handle:
                return handle.read()

        raise RuntimeError('OpenAI image response did not contain image bytes')

    def _generate_fallback_image(
        self,
        *,
        prompt: str,
        mode: str,
        style: str | None,
        aspect_ratio: str | None,
        source_image: bytes | None,
    ) -> bytes:
        width, height = self._aspect_ratio_to_dims(aspect_ratio)

        if mode in {'photo', 'recolor'} and source_image:
            return self._photo_to_line_art(source_image, width, height)

        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)

        headline = (prompt or 'Coloring Page').strip()[:56]
        subline = (style or 'clean outlines').strip()[:40]

        # Draw decorative line-art style objects.
        margin = 48
        draw.rectangle([margin, margin, width - margin, height - margin], outline='black', width=4)
        draw.ellipse([margin + 40, margin + 120, width // 2, height // 2], outline='black', width=4)
        draw.polygon(
            [
                (width // 2 + 40, height // 2 + 20),
                (width - margin - 40, height // 2 + 120),
                (width // 2 + 120, height - margin - 40),
            ],
            outline='black',
            width=4,
        )

        # Keep text lightweight so output remains printable.
        draw.text((margin + 24, margin + 24), 'COLORFULME', fill='black')
        draw.text((margin + 24, height - margin - 44), headline, fill='black')
        draw.text((margin + 24, height - margin - 24), subline, fill='black')

        return self._to_png_bytes(image)

    def _photo_to_line_art(self, source_bytes: bytes, width: int, height: int) -> bytes:
        image = Image.open(BytesIO(source_bytes)).convert('RGB')
        image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(image)
        gray = gray.filter(ImageFilter.MedianFilter(size=3))
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.autocontrast(edges)

        # Invert and threshold for clean coloring outlines.
        inv = ImageOps.invert(edges)
        line_art = inv.point(lambda p: 255 if p > 170 else 0)
        line_art = line_art.convert('RGB')
        return self._to_png_bytes(line_art)

    def _to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()

    @staticmethod
    def _aspect_ratio_to_size(aspect_ratio: str | None) -> str:
        mapping = {
            '1:1': '1024x1024',
            '4:5': '1024x1280',
            '3:4': '1024x1365',
            '16:9': '1536x1024',
            '9:16': '1024x1536',
        }
        size = mapping.get((aspect_ratio or '').strip(), '1024x1024')
        # Keep requests within documented image API sizes.
        if size not in {'1024x1024', '1024x1536', '1536x1024'}:
            return '1024x1024'
        return size

    @staticmethod
    def _aspect_ratio_to_dims(aspect_ratio: str | None) -> tuple[int, int]:
        mapping = {
            '1:1': (1200, 1200),
            '4:5': (1200, 1500),
            '3:4': (1200, 1600),
            '16:9': (1600, 900),
            '9:16': (900, 1600),
        }
        return mapping.get((aspect_ratio or '').strip(), (1200, 1200))

    @staticmethod
    def _normalize_quality(value: str) -> str:
        cleaned = (value or '').strip().lower()
        if cleaned in {'low', 'medium', 'high', 'auto'}:
            return cleaned
        return 'medium'

    def _candidate_models(self, primary: str) -> list[str]:
        primary = (primary or '').strip() or self.model
        fallback = (self.fallback_model or '').strip()
        seen = set()
        models = []
        for item in [primary, fallback]:
            if item and item not in seen:
                seen.add(item)
                models.append(item)
        return models or ['gpt-image-1.5']

    @staticmethod
    def estimate_image_cost_usd(model: str, quality: str, size: str) -> float | None:
        pricing_key = OpenAIClient._pricing_key(model)
        if pricing_key is None:
            return None

        quality_costs = _IMAGE_PRICE_USD.get(pricing_key, {}).get((quality or '').strip().lower())
        if not quality_costs:
            return None
        return quality_costs.get(size)

    @staticmethod
    def _pricing_key(model: str) -> str | None:
        value = (model or '').strip().lower()
        if value.startswith('gpt-image-1.5'):
            return 'gpt-image-1.5'
        if value.startswith('gpt-image-1-mini'):
            return 'gpt-image-1-mini'
        if value.startswith('gpt-image-1'):
            return 'gpt-image-1'
        return None
