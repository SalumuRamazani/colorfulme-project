from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List, Tuple


_BANNED_TERMS = {
    'nude',
    'naked',
    'sexual',
    'porn',
    'explicit',
    'gore',
    'violent',
    'blood',
    'weapon',
    'hate',
    'abuse',
}


class ProgrammaticFillService:
    def fill_entry(
        self,
        entry: Dict[str, object],
        *,
        force: bool = False,
        batch_id: str | None = None,
    ) -> Tuple[Dict[str, object], List[str]]:
        updated = deepcopy(entry)
        changes: List[str] = []

        title = self._safe_text(updated.get('title'))
        route_path = self._safe_text(updated.get('route_path'))
        entry_type = self._safe_text(updated.get('entry_type')).lower()

        primary_keyword = self._safe_text(updated.get('primary_keyword')) or self._default_primary_keyword(title)
        if primary_keyword != self._safe_text(updated.get('primary_keyword')):
            updated['primary_keyword'] = primary_keyword
            changes.append('primary_keyword')

        secondary_keywords = list(updated.get('secondary_keywords') or [])
        if force or not secondary_keywords:
            derived_secondary = self._default_secondary_keywords(title, primary_keyword)
            if derived_secondary != secondary_keywords:
                updated['secondary_keywords'] = derived_secondary
                changes.append('secondary_keywords')

        content_brief = self._safe_text(updated.get('content_brief'))
        if not content_brief:
            content_brief = self._default_content_brief(entry_type, title)
            updated['content_brief'] = content_brief
            changes.append('content_brief')

        current_meta = self._safe_text(updated.get('meta_description'))
        if force or self._meta_is_stale(current_meta):
            meta = self._build_meta_description(title, primary_keyword)
            if meta != current_meta:
                updated['meta_description'] = meta
                changes.append('meta_description')

        current_intro = self._safe_text(updated.get('intro'))
        if force or self._intro_is_stale(current_intro):
            intro = self._build_intro(title, primary_keyword, content_brief)
            if intro != current_intro:
                updated['intro'] = intro
                updated['intro_paragraphs'] = [intro]
                changes.append('intro')

        current_seed_prompt = self._safe_text(updated.get('generation_seed_prompt'))
        if force or not current_seed_prompt:
            seed_prompt = self._build_seed_prompt(title, primary_keyword)
            if seed_prompt != current_seed_prompt:
                updated['generation_seed_prompt'] = seed_prompt
                changes.append('generation_seed_prompt')

        current_body = self._safe_text(updated.get('body'))
        if force or self._body_is_stale(current_body):
            body = self._build_body(
                title=title,
                route_path=route_path,
                primary_keyword=primary_keyword,
                secondary_keywords=list(updated.get('secondary_keywords') or []),
            )
            if body != current_body:
                updated['body'] = body
                updated['body_paragraphs'] = [paragraph.strip() for paragraph in body.split('\n\n') if paragraph.strip()]
                changes.append('body')

        should_enforce_detail_blocks = self._requires_detail_blocks(entry_type, route_path)
        feature_bullets = list(updated.get('feature_bullets') or [])
        if force or (should_enforce_detail_blocks and len(feature_bullets) < 3):
            bullets = self._build_feature_bullets(primary_keyword)
            if bullets != feature_bullets:
                updated['feature_bullets'] = bullets
                changes.append('feature_bullets')

        faq_items = list(updated.get('faq') or [])
        if force or (should_enforce_detail_blocks and len(faq_items) < 2):
            faq = self._build_faq(primary_keyword)
            if faq != faq_items:
                updated['faq'] = faq
                changes.append('faq')

        self._sanitize_entry(updated)

        if changes:
            now = datetime.now(timezone.utc).isoformat()
            updated['updated_at'] = now
            updated['last_generated_at'] = now
            if batch_id:
                updated['generation_batch_id'] = batch_id
            if self._safe_text(updated.get('content_status')).lower() != 'approved':
                updated['content_status'] = 'generated'

        return updated, sorted(set(changes))

    @staticmethod
    def _safe_text(value: object) -> str:
        if value is None:
            return ''
        return str(value).strip()

    def _sanitize_entry(self, entry: Dict[str, object]) -> None:
        for key in ('meta_description', 'intro', 'body', 'content_brief', 'qa_notes'):
            text = self._safe_text(entry.get(key))
            if text:
                entry[key] = self._sanitize_family_safe(text)

        bullets = [self._sanitize_family_safe(self._safe_text(item)) for item in list(entry.get('feature_bullets') or [])]
        entry['feature_bullets'] = [item for item in bullets if item]

        faq_items = []
        for item in list(entry.get('faq') or []):
            question = self._sanitize_family_safe(self._safe_text(item.get('question')))
            answer = self._sanitize_family_safe(self._safe_text(item.get('answer')))
            if question:
                faq_items.append({'question': question, 'answer': answer})
        entry['faq'] = faq_items

    def _sanitize_family_safe(self, text: str) -> str:
        result = text
        for term in _BANNED_TERMS:
            pattern = re.compile(rf'\b{re.escape(term)}\b', flags=re.IGNORECASE)
            result = pattern.sub('family-friendly', result)
        return result

    def _default_primary_keyword(self, title: str) -> str:
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', title).strip().lower()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned or 'coloring pages'

    def _default_secondary_keywords(self, title: str, primary_keyword: str) -> List[str]:
        base = self._default_primary_keyword(title)
        words = [word for word in base.split(' ') if word]
        focus = words[:2] if len(words) >= 2 else words
        topic = ' '.join(focus) if focus else primary_keyword
        return [
            f'{topic} printable',
            f'{topic} for kids',
            'free coloring pages',
            'pdf coloring page download',
        ]

    def _default_content_brief(self, entry_type: str, title: str) -> str:
        if entry_type == 'tool':
            return f'Explain how to use {title} quickly and safely, with practical steps and printable outcomes.'
        if entry_type == 'library':
            return f'Showcase {title} as an example library asset and guide users to generate related pages.'
        return f'Provide helpful, family-safe information about {title} and direct users to create printable pages.'

    @staticmethod
    def _word_count(text: str) -> int:
        return len([item for item in re.split(r'\s+', text.strip()) if item])

    def _meta_is_stale(self, value: str) -> bool:
        return not value or len(value) < 120 or len(value) > 160

    def _intro_is_stale(self, value: str) -> bool:
        words = self._word_count(value)
        return not value or words < 30 or words > 60 or '\n\n' in value

    def _body_is_stale(self, value: str) -> bool:
        if not value:
            return True
        paragraphs = [part for part in value.split('\n\n') if part.strip()]
        if len(paragraphs) < 3:
            return True
        for paragraph in paragraphs:
            if self._word_count(paragraph) > 130:
                return True
        return self._word_count(value) < 220

    @staticmethod
    def _requires_detail_blocks(entry_type: str, route_path: str) -> bool:
        if entry_type == 'tool':
            return True
        return entry_type == 'page' and not route_path.startswith('/blog/')

    def _fit_meta_length(self, value: str, minimum: int = 120, maximum: int = 160) -> str:
        text = re.sub(r'\s+', ' ', value).strip()
        if len(text) < minimum:
            extra = ' Fast workflow, clear outlines, and instant print-ready PNG and PDF exports.'
            text = (text + extra)[:maximum]
        if len(text) > maximum:
            text = text[: maximum - 1]
            if ' ' in text:
                text = text.rsplit(' ', 1)[0]
            text = text.rstrip(' ,;:.') + '.'
        return text

    def _build_meta_description(self, title: str, primary_keyword: str) -> str:
        base = (
            f"{title} on ColorfulMe. Create {primary_keyword} with family-safe prompts, clean printable outlines, "
            "and one-click PNG or PDF downloads for home, classrooms, and activity books."
        )
        return self._fit_meta_length(base)

    def _build_intro(self, title: str, primary_keyword: str, brief: str) -> str:
        text = (
            f"{title} helps you create {primary_keyword} in seconds using a guided, family-safe workflow. "
            f"Use this page to get clear printable line art, practical prompt ideas, and export-ready files for "
            f"school activities, home crafts, and quick print projects. {brief}"
        )
        text = re.sub(r'\s+', ' ', text).strip()
        words = text.split(' ')
        if len(words) < 30:
            words += [
                'You',
                'can',
                'start',
                'from',
                'text',
                'or',
                'photo',
                'and',
                'download',
                'instantly.',
            ]
        if len(words) > 60:
            words = words[:60]
        return ' '.join(words)

    def _build_body(self, *, title: str, route_path: str, primary_keyword: str, secondary_keywords: List[str]) -> str:
        secondary = ', '.join(secondary_keywords[:3]) if secondary_keywords else 'printable sheets and prompt ideas'
        paragraph_one = (
            f"{title} helps parents, teachers, and creators produce dependable {primary_keyword} pages with less editing. "
            "Use one clear subject, one scene, and a family-safe tone so the generated outline stays simple and printable. "
            "When prompts are focused, the result is cleaner line art with open spaces that are easier for kids to color."
        )

        paragraph_two = (
            f"This page covers popular searches such as {secondary} and gives you a repeatable flow for high-quality results. "
            "Start with a short style instruction like clean line art, then keep details age-appropriate and easy to print. "
            "If a preview looks too busy, remove extra objects and regenerate with fewer scene elements."
        )

        paragraph_three = (
            "After generation, download PNG for digital coloring or PDF for print packs. "
            "For classroom use, test one page first, then keep the same prompt pattern for the rest of the set. "
            f"For {route_path}, this approach keeps quality consistent while reducing rewrite time each time you refresh content. "
            "You can also save successful prompt variations by age group so teams can launch new themed pages faster."
        )

        paragraph_four = (
            f"To improve outcomes over time, keep notes on which {primary_keyword} prompts produce the clearest outlines. "
            "Reuse those winning prompt styles for future pages, and adjust only subject details so each new sheet stays unique "
            "without losing readability, print quality, or family-safe tone."
        )

        return f"{paragraph_one}\n\n{paragraph_two}\n\n{paragraph_three}\n\n{paragraph_four}"

    @staticmethod
    def _build_seed_prompt(title: str, primary_keyword: str) -> str:
        return (
            f"Create a family-safe printable coloring page for {title}. "
            f"Theme focus: {primary_keyword}. "
            "Use bold black outlines, white background, and clear open areas for coloring."
        )

    @staticmethod
    def _build_feature_bullets(primary_keyword: str) -> List[str]:
        return [
            f'Generate {primary_keyword} with family-safe prompt handling.',
            'Produce clean outlines that print clearly on standard paper.',
            'Download PNG and PDF files instantly for classroom or home use.',
        ]

    @staticmethod
    def _build_faq(primary_keyword: str) -> List[Dict[str, str]]:
        return [
            {
                'question': f'Can I use this for {primary_keyword}?',
                'answer': 'Yes. The workflow is optimized for printable line art and repeatable prompt quality.',
            },
            {
                'question': 'How do I keep pages family-safe?',
                'answer': 'Use age-appropriate prompts and keep sensitive topics out of the request. Unsafe input is filtered.',
            },
        ]
