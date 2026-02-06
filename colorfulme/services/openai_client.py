from __future__ import annotations

import base64
from io import BytesIO
import logging
from urllib.request import urlopen

from flask import current_app
from PIL import Image, ImageDraw, ImageFilter, ImageOps


class OpenAIClient:
    def __init__(self):
        self.api_key = (current_app.config.get('OPENAI_API_KEY') or '').strip()
        self.model = current_app.config.get('OPENAI_MODEL', 'gpt-image-1')
        self.allow_fake = bool(current_app.config.get('ALLOW_FAKE_AI', True))

    def generate_image(
        self,
        *,
        prompt: str,
        mode: str,
        style: str | None = None,
        aspect_ratio: str | None = None,
        source_image: bytes | None = None,
    ) -> bytes:
        if self.api_key:
            try:
                return self._generate_openai_image(
                    prompt=prompt,
                    mode=mode,
                    style=style,
                    aspect_ratio=aspect_ratio,
                )
            except Exception as exc:
                if not self.allow_fake:
                    raise
                logging.warning('OpenAI generation failed, using deterministic fallback: %s', exc)

        if not self.allow_fake:
            raise RuntimeError('OpenAI API key is missing and ALLOW_FAKE_AI is disabled')
        return self._generate_fallback_image(
            prompt=prompt,
            mode=mode,
            style=style,
            aspect_ratio=aspect_ratio,
            source_image=source_image,
        )

    def _generate_openai_image(self, *, prompt: str, mode: str, style: str | None, aspect_ratio: str | None) -> bytes:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        size = self._aspect_ratio_to_size(aspect_ratio)
        style_label = (style or 'clean line art').strip()
        system_prompt = (
            'Create a black-and-white printable coloring page. '
            'No grayscale fills, only clear outlines, family-safe content, white background.'
        )

        user_prompt = f"Mode: {mode}. Style: {style_label}. Request: {prompt}" if style_label else prompt

        response = client.images.generate(
            model=self.model,
            prompt=f"{system_prompt}\n\n{user_prompt}",
            size=size,
            quality='high',
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
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.autocontrast(edges)

        # Invert and threshold for clean coloring outlines.
        inv = ImageOps.invert(edges)
        line_art = inv.point(lambda p: 255 if p > 160 else 0)
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
        return mapping.get((aspect_ratio or '').strip(), '1024x1024')

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
