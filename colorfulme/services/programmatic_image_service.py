from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

from flask import current_app

from colorfulme.services.openai_client import OpenAIClient
from colorfulme.utils.slug import slugify


class ProgrammaticImageService:
    def __init__(self):
        self.client = OpenAIClient()
        self.model = 'gpt-image-1-mini'
        self.quality = 'medium'

    def process_entry(
        self,
        entry: Dict[str, object],
        *,
        force: bool = False,
        dry_run: bool = False,
        batch_id: str | None = None,
    ) -> Tuple[Dict[str, object], Dict[str, object]]:
        updated = deepcopy(entry)

        prompt = self._build_prompt(updated)
        signature = self._signature(updated, prompt)
        slug = slugify(str(updated.get('slug') or updated.get('title') or updated.get('route_path') or 'page'))

        relative_asset_path = f'static/images/programmatic/{slug}-hero.png'
        public_url = f'/static/images/programmatic/{slug}-hero.png'

        should_generate, reason = self._needs_generation(updated, signature=signature, public_url=public_url, force=force)
        if not should_generate:
            return updated, {
                'status': 'skipped',
                'reason': reason,
                'route_path': updated.get('route_path', ''),
                'image_url': updated.get('image_url', ''),
            }

        if dry_run:
            return updated, {
                'status': 'would_generate',
                'reason': reason,
                'route_path': updated.get('route_path', ''),
                'image_url': public_url,
                'asset_local_path': relative_asset_path,
            }

        try:
            render = self.client.generate_image(
                prompt=prompt,
                mode='text',
                style=(str(updated.get('image_style') or '').strip() or 'clean line art'),
                aspect_ratio=(str(updated.get('image_aspect_ratio') or '').strip() or '4:5'),
                model=self.model,
                quality=self.quality,
                source_image=None,
            )

            output_file = self._absolute_local_path(public_url)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(render.png_bytes)

            now = datetime.now(timezone.utc).isoformat()
            updated['image_url'] = public_url
            updated['asset_local_path'] = relative_asset_path
            updated['asset_hash'] = signature
            updated['last_generated_at'] = now
            updated['updated_at'] = now
            if batch_id:
                updated['generation_batch_id'] = batch_id
            if str(updated.get('image_status') or '').lower() != 'approved':
                updated['image_status'] = 'generated'

            return updated, {
                'status': 'generated',
                'reason': reason,
                'route_path': updated.get('route_path', ''),
                'image_url': public_url,
                'asset_local_path': relative_asset_path,
                'model': render.model,
                'quality': render.quality,
            }
        except Exception as exc:
            updated['image_status'] = 'failed'
            updated['qa_notes'] = self._merge_note(str(updated.get('qa_notes') or ''), f'image_generation_error: {exc}')
            return updated, {
                'status': 'failed',
                'reason': str(exc),
                'route_path': updated.get('route_path', ''),
            }

    def _needs_generation(self, entry: Dict[str, object], *, signature: str, public_url: str, force: bool) -> Tuple[bool, str]:
        if force:
            return True, 'force-images enabled'

        image_url = str(entry.get('image_url') or '').strip()
        asset_hash = str(entry.get('asset_hash') or '').strip()

        if not image_url:
            return True, 'missing image_url'

        if image_url == '/static/images/colorfulme/hero-samples.svg':
            return True, 'broken placeholder image reference'

        if image_url.startswith('/static/'):
            existing = self._absolute_local_path(image_url)
            if not existing.exists():
                return True, 'local image file missing'

        if image_url != public_url:
            return True, 'non-canonical image path'

        if not asset_hash:
            return True, 'missing asset hash'

        if asset_hash != signature:
            return True, 'signature changed'

        return False, 'image already up to date'

    def _build_prompt(self, entry: Dict[str, object]) -> str:
        override = str(entry.get('image_prompt_override') or '').strip()
        if override:
            return override

        seed = str(entry.get('generation_seed_prompt') or '').strip()
        if seed:
            return seed

        title = str(entry.get('title') or 'coloring page').strip()
        primary_keyword = str(entry.get('primary_keyword') or '').strip()
        keyword_phrase = f' around {primary_keyword}' if primary_keyword else ''
        return (
            f'Create a black and white printable coloring page for "{title}"{keyword_phrase}. '
            'Use thick clean outlines, simple closed shapes, white background, and family-safe friendly composition.'
        )

    def _signature(self, entry: Dict[str, object], prompt: str) -> str:
        payload = {
            'prompt': prompt,
            'image_style': str(entry.get('image_style') or '').strip() or 'clean line art',
            'image_aspect_ratio': str(entry.get('image_aspect_ratio') or '').strip() or '4:5',
            'model': self.model,
            'quality': self.quality,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    def _absolute_local_path(self, public_url: str) -> Path:
        clean = public_url.split('?', 1)[0].split('#', 1)[0]
        if not clean.startswith('/static/'):
            raise ValueError(f'Expected /static/ URL, got: {public_url}')

        relative = clean[len('/static/'):]
        return Path(current_app.static_folder) / relative

    @staticmethod
    def _merge_note(existing: str, new_note: str) -> str:
        existing = (existing or '').strip()
        if not existing:
            return new_note
        if new_note in existing:
            return existing
        return f'{existing} | {new_note}'
