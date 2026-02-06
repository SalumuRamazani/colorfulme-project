from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from models import ApiKey, GenerationJob
from colorfulme.services.credits_service import ensure_wallet_for_user, get_active_plan
from colorfulme.services.programmatic_service import ProgrammaticService


web_bp = Blueprint('web', __name__)

CORE_GENERATOR_ORDER = [
    '/ai-coloring-page-generator',
    '/photo-to-coloring-page-converter',
    '/photo-to-sketch',
    '/family-photo-coloring-page',
    '/coloring-book-generator',
    '/generators/name-coloring-page-generator',
    '/generators/bible-verse-coloring-page-generator',
    '/generators/quote-coloring-page-generator',
    '/generators/bubble-letter-coloring-page-generator',
    '/generators/graffiti-coloring-page-generator',
    '/generators/rainy-day-activities',
    '/generators/classroom-activities',
]

PROMPT_GENERATOR_ORDER = [
    '/prompt-generators/midjourney-prompt-generator',
    '/prompt-generators/flux-prompt-generator',
    '/prompt-generators/stable-diffusion-prompt-generator',
    '/prompt-generators/image-prompt-generator',
    '/prompt-generators/drawing-prompt-generator',
    '/prompt-generators/image-to-prompt-generator',
    '/prompt-generators/recraft-prompt-generator',
]


def _published_tools():
    tools = [
        entry
        for entry in ProgrammaticService.get_entries_by_type('tool')
        if entry.get('status') == 'published'
    ]
    deduped = {}
    for entry in tools:
        route_path = entry.get('route_path')
        if route_path and route_path not in deduped:
            deduped[route_path] = entry

    tools = list(deduped.values())
    tools.sort(key=lambda entry: (entry.get('title') or '').lower())
    return tools


def _ordered_subset(tools, ordered_paths):
    by_path = {entry.get('route_path'): entry for entry in tools if entry.get('route_path')}
    ordered = [by_path[path] for path in ordered_paths if path in by_path]
    if ordered:
        return ordered
    return tools


@web_bp.get('/health')
def health_check():
    return jsonify({'status': 'ok', 'service': 'colorfulme'})


@web_bp.get('/')
def index():
    featured_library = [
        entry for entry in ProgrammaticService.get_entries_by_type('library') if entry.get('status') == 'published'
    ][:6]
    return render_template('index.html', featured_library=featured_library)


@web_bp.get('/create')
def create_page():
    return render_template('create.html')


@web_bp.get('/library')
def library_page():
    items = [
        entry for entry in ProgrammaticService.get_entries_by_type('library') if entry.get('status') == 'published'
    ]
    return render_template('library.html', items=items)


@web_bp.get('/generators')
def generators_page():
    tools = _published_tools()
    prompt_tools = [
        tool
        for tool in tools
        if str(tool.get('route_path', '')).startswith('/prompt-generators/')
        or 'prompt-generator' in str(tool.get('route_path', ''))
    ]
    core_tools = [tool for tool in tools if tool not in prompt_tools]
    core_tools = _ordered_subset(core_tools, CORE_GENERATOR_ORDER)
    prompt_tools = _ordered_subset(prompt_tools, PROMPT_GENERATOR_ORDER)
    return render_template('generators.html', core_tools=core_tools, prompt_tools=prompt_tools)


@web_bp.get('/prompt-generators')
def prompt_generators_page():
    prompt_tools = [
        tool
        for tool in _published_tools()
        if str(tool.get('route_path', '')).startswith('/prompt-generators/')
        or 'prompt-generator' in str(tool.get('route_path', ''))
    ]
    prompt_tools = _ordered_subset(prompt_tools, PROMPT_GENERATOR_ORDER)
    return render_template('prompt_generators.html', prompt_tools=prompt_tools)


@web_bp.get('/blog')
def blog_index():
    entries = [
        entry
        for entry in ProgrammaticService.get_entries()
        if entry.get('status') == 'published' and str(entry.get('route_path', '')).startswith('/blog/')
    ]
    entries.sort(key=lambda item: item.get('updated_at', ''), reverse=True)
    return render_template('blog.html', posts=entries)


@web_bp.get('/blog/<slug>')
def blog_post(slug: str):
    target_path = f'/blog/{slug}'
    entry = ProgrammaticService.get_published_index().get(target_path)
    if not entry:
        abort(404)
    return render_template('blog_post.html', post=entry)


@web_bp.get('/dashboard')
@login_required
def dashboard():
    wallet = ensure_wallet_for_user(current_user)
    plan = get_active_plan(current_user)
    jobs = (
        GenerationJob.query.filter_by(user_id=current_user.id)
        .order_by(GenerationJob.created_at.desc())
        .limit(15)
        .all()
    )
    api_keys = ApiKey.query.filter_by(user_id=current_user.id, is_active=True).order_by(ApiKey.created_at.desc()).all()
    return render_template('dashboard.html', wallet=wallet, plan=plan, jobs=jobs, api_keys=api_keys)


@web_bp.get('/assets/local/<path:key>')
def local_asset(key: str):
    # Local development/static fallback only.
    base = Path(current_app.instance_path) / 'generated'
    target = base / key
    if not target.exists() or not target.is_file():
        abort(404)

    as_download = request.args.get('download') == '1'
    return send_file(target, as_attachment=as_download)
