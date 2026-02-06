from __future__ import annotations

import logging
from typing import Tuple

from flask import current_app


BLOCKED_TERMS = {
    'nude',
    'nudity',
    'porn',
    'sexual',
    'gore',
    'blood',
    'dismemberment',
    'kill',
    'weapon',
    'hate',
    'racist',
    'self-harm',
    'suicide',
    'nsfw',
}


class ModerationService:
    def __init__(self):
        self.strict_mode = bool(current_app.config.get('STRICT_MODERATION', True))
        self.api_key = (current_app.config.get('OPENAI_API_KEY') or current_app.config.get('OPENAI_API_KEY'.lower()) or '').strip()

    def check_prompt(self, prompt: str) -> Tuple[bool, str | None]:
        text = (prompt or '').lower().strip()
        if not text:
            return False, 'Prompt is required.'

        # Local deterministic safety gate for strict family-safe mode.
        if self.strict_mode:
            for term in BLOCKED_TERMS:
                if term in text:
                    return False, f"Prompt blocked by safety policy ({term})."

        # Optional upstream moderation; local strict checks already enforce baseline.
        try:
            self._openai_moderation_check(text)
        except Exception as exc:
            logging.warning('OpenAI moderation check skipped/failed: %s', exc)

        return True, None

    def _openai_moderation_check(self, text: str) -> None:
        if not self.api_key:
            return

        try:
            from openai import OpenAI
        except Exception:
            return

        client = OpenAI(api_key=self.api_key)
        response = client.moderations.create(model='omni-moderation-latest', input=text)
        results = getattr(response, 'results', []) or []
        if results and getattr(results[0], 'flagged', False):
            raise ValueError('Prompt blocked by upstream moderation.')
