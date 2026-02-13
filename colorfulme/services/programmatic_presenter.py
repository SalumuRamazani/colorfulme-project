from __future__ import annotations

import re
from typing import Dict, List


SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _safe_text(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def _normalize_paragraphs(entry: Dict[str, object]) -> List[str]:
    body_paragraphs = entry.get('body_paragraphs')
    if isinstance(body_paragraphs, list):
        normalized = [_safe_text(item) for item in body_paragraphs if _safe_text(item)]
        if normalized:
            return normalized

    body = _safe_text(entry.get('body'))
    if body:
        normalized = [_safe_text(item) for item in body.split('\n\n') if _safe_text(item)]
        if normalized:
            return normalized

    intro = _safe_text(entry.get('intro'))
    if intro:
        return [intro]

    return []


def _split_sentences(paragraph: str) -> List[str]:
    normalized = re.sub(r'\s+', ' ', paragraph).strip()
    if not normalized:
        return []

    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
    if sentences:
        return sentences
    return [normalized]


def _chunk_sentences(sentences: List[str], min_words: int = 45, max_words: int = 85) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = _word_count(sentence)
        if current and current_words + sentence_words > max_words:
            chunks.append(' '.join(current))
            current = [sentence]
            current_words = sentence_words
            continue

        current.append(sentence)
        current_words += sentence_words
        if current_words >= min_words:
            chunks.append(' '.join(current))
            current = []
            current_words = 0

    if current:
        chunks.append(' '.join(current))

    return [chunk for chunk in chunks if _safe_text(chunk)]


def _chunk_paragraphs(paragraphs: List[str]) -> List[str]:
    chunks: List[str] = []
    for paragraph in paragraphs:
        sentences = _split_sentences(paragraph)
        chunks.extend(_chunk_sentences(sentences))
    return chunks


def _extract_primary_keyword(entry: Dict[str, object]) -> str:
    keyword = _safe_text(entry.get('primary_keyword'))
    if keyword:
        return keyword
    title = _safe_text(entry.get('title'))
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
    return cleaned or 'printable coloring pages'


def _default_intro(title: str, keyword: str) -> str:
    return (
        f'{title} helps families and teachers create {keyword} quickly with printable line-art '
        'that is clean, kid-friendly, and easy to use at home or in class.'
    )


def _default_section_text(kind: str, keyword: str, route_path: str) -> str:
    if kind == 'how_to':
        return (
            f'Start with a clear subject for {keyword}, keep your wording simple, and include an age-appropriate '
            f'style note. Generate a preview, refine details in one short prompt update, then download PNG or PDF '
            f'for route {route_path or "this page"}.'
        )
    return (
        f'Use this page to build {keyword} with consistent outlines, practical prompts, and print-ready downloads. '
        'Keep scenes simple, focus on one idea per page, and prioritize open shapes that are easy to color.'
    )


def _build_section_chunks(chunks: List[str], keyword: str, route_path: str) -> Dict[str, List[str]]:
    if not chunks:
        chunks = [_default_section_text('overview', keyword, route_path)]

    overview: List[str]
    how_to_use: List[str]
    practical_tips: List[str]

    if len(chunks) >= 5:
        overview = chunks[:2]
        how_to_use = chunks[2:4]
        practical_tips = chunks[4:]
    elif len(chunks) == 4:
        overview = chunks[:2]
        how_to_use = [chunks[2]]
        practical_tips = [chunks[3]]
    elif len(chunks) == 3:
        overview = [chunks[0]]
        how_to_use = [chunks[1]]
        practical_tips = [chunks[2]]
    elif len(chunks) == 2:
        overview = [chunks[0]]
        how_to_use = [chunks[1]]
        practical_tips = [_default_section_text('tips', keyword, route_path)]
    else:
        overview = [chunks[0]]
        how_to_use = [_default_section_text('how_to', keyword, route_path)]
        practical_tips = [_default_section_text('tips', keyword, route_path)]

    return {
        'overview': [_safe_text(item) for item in overview if _safe_text(item)],
        'how_to_use': [_safe_text(item) for item in how_to_use if _safe_text(item)],
        'practical_tips': [_safe_text(item) for item in practical_tips if _safe_text(item)],
    }


def _normalize_faq(entry: Dict[str, object]) -> List[Dict[str, str]]:
    faq_items = entry.get('faq')
    normalized: List[Dict[str, str]] = []
    if isinstance(faq_items, list):
        for item in faq_items:
            question = _safe_text((item or {}).get('question'))
            answer = _safe_text((item or {}).get('answer'))
            if question:
                normalized.append({'question': question, 'answer': answer})
    return normalized


def _normalize_related(related_categories: List[Dict[str, object]] | None) -> List[Dict[str, str]]:
    if not related_categories:
        return []
    normalized = []
    for item in related_categories:
        title = _safe_text(item.get('title'))
        route_path = _safe_text(item.get('route_path'))
        if not title or not route_path:
            continue
        normalized.append({'title': title, 'route_path': route_path})
    return normalized


def _detect_audience(route_path: str, title: str) -> str:
    route = route_path.lower()
    text = title.lower()
    if 'toddler' in route or 'toddler' in text:
        return 'Toddlers'
    if 'preschool' in route or 'preschool' in text:
        return 'Preschoolers'
    if 'teen' in route or 'teen' in text:
        return 'Teens'
    if 'adult' in route or 'adult' in text:
        return 'Adults'
    if 'senior' in route or 'senior' in text:
        return 'Seniors'
    if 'kid' in route or 'kids' in text:
        return 'Kids'
    return 'Kids, families, classrooms'


def _derive_how_to_steps(keyword: str) -> List[str]:
    return [
        f'Pick one clear subject for {keyword} and keep wording simple.',
        'Add a short style note such as bold outlines and open coloring areas.',
        'Generate a preview and refine details with one short follow-up prompt.',
        'Download PNG or PDF and print on standard letter or A4 paper.',
    ]


def _derive_practical_tips(entry: Dict[str, object], keyword: str) -> List[str]:
    bullet_items = entry.get('feature_bullets')
    if isinstance(bullet_items, list):
        normalized = [_safe_text(item) for item in bullet_items if _safe_text(item)]
        if len(normalized) >= 3:
            return normalized[:6]

    return [
        f'Use age-appropriate wording for {keyword} to keep results family-friendly.',
        'Prefer one scene per page to improve line clarity and print quality.',
        'Use high-contrast printer settings for crisp outlines and easy coloring.',
    ]


def build_entry_view_model(
    entry: Dict[str, object],
    page_kind: str,
    related_categories: List[Dict[str, object]] | None = None,
) -> Dict[str, object]:
    title = _safe_text(entry.get('h1')) or _safe_text(entry.get('title')) or 'Coloring Page'
    route_path = _safe_text(entry.get('route_path'))
    keyword = _extract_primary_keyword(entry)

    intro = _safe_text(entry.get('intro')) or _safe_text(entry.get('meta_description'))
    if not intro:
        intro = _default_intro(title, keyword)

    paragraphs = _normalize_paragraphs(entry)
    chunks = _chunk_paragraphs(paragraphs)
    section_chunks = _build_section_chunks(chunks, keyword, route_path)

    entry_type = _safe_text(entry.get('entry_type')).lower() or 'page'
    entry_type_label = entry_type.title()
    page_kind_label = 'Free Category' if page_kind == 'category' else 'Programmatic Page'

    content_sections = [
        {
            'id': 'overview',
            'title': 'Overview',
            'paragraphs': section_chunks['overview'],
        },
        {
            'id': 'how_to_use',
            'title': 'How To Use This Page',
            'paragraphs': section_chunks['how_to_use'],
        },
        {
            'id': 'practical_tips',
            'title': 'Practical Tips',
            'paragraphs': section_chunks['practical_tips'],
        },
    ]

    quick_facts = [
        {'label': 'Formats', 'value': 'PNG + PDF'},
        {'label': 'Audience', 'value': _detect_audience(route_path, title)},
        {'label': 'Safety', 'value': 'Family-safe moderation'},
        {'label': 'Page type', 'value': entry_type_label},
    ]

    hero_badges = [page_kind_label, 'Printable', 'Family-safe']

    faq_items = _normalize_faq(entry)
    related_links = _normalize_related(related_categories)

    primary_cta_label = _safe_text(entry.get('primary_cta_label')) or 'Create Coloring Page'
    primary_cta_url = _safe_text(entry.get('primary_cta_url')) or '/create'
    secondary_cta_label = _safe_text(entry.get('secondary_cta_label')) or 'Browse Categories'
    secondary_cta_url = _safe_text(entry.get('secondary_cta_url')) or '/free-coloring-pages'

    return {
        'hero_title': title,
        'hero_intro': intro,
        'hero_image_url': _safe_text(entry.get('image_url')),
        'hero_badges': hero_badges,
        'content_sections': content_sections,
        'quick_facts': quick_facts,
        'faq_items': faq_items,
        'related_links': related_links,
        'how_to_steps': _derive_how_to_steps(keyword),
        'practical_tips': _derive_practical_tips(entry, keyword),
        'primary_cta_label': primary_cta_label,
        'primary_cta_url': primary_cta_url,
        'secondary_cta_label': secondary_cta_label,
        'secondary_cta_url': secondary_cta_url,
    }
