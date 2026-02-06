from __future__ import annotations

from datetime import datetime

from flask import Blueprint, Response, render_template, request

from colorfulme.services.programmatic_service import ProgrammaticService


seo_bp = Blueprint('seo', __name__)


@seo_bp.get('/programmatic/content')
def programmatic_registry():
    manifest = ProgrammaticService.get_manifest()
    entries = sorted(ProgrammaticService.get_entries(), key=lambda item: item.get('route_path', ''))
    return render_template('programmatic_index.html', manifest=manifest, entries=entries)


@seo_bp.get('/sitemap.xml')
def sitemap_xml():
    now = datetime.utcnow().strftime('%Y-%m-%d')
    base = request.url_root.rstrip('/')

    pages = [
        {'loc': f'{base}/', 'priority': '1.0'},
        {'loc': f'{base}/create', 'priority': '0.95'},
        {'loc': f'{base}/generators', 'priority': '0.92'},
        {'loc': f'{base}/prompt-generators', 'priority': '0.9'},
        {'loc': f'{base}/library', 'priority': '0.9'},
        {'loc': f'{base}/pricing', 'priority': '0.85'},
        {'loc': f'{base}/blog', 'priority': '0.8'},
    ]

    for entry in ProgrammaticService.get_published_index().values():
        pages.append(
            {
                'loc': f"{base}{entry.get('route_path')}",
                'priority': '0.8' if entry.get('entry_type') != 'tool' else '0.85',
                'lastmod': entry.get('updated_at') or now,
            }
        )

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for page in pages:
        xml.append('  <url>')
        xml.append(f"    <loc>{page['loc']}</loc>")
        xml.append(f"    <lastmod>{page.get('lastmod', now)}</lastmod>")
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append(f"    <priority>{page['priority']}</priority>")
        xml.append('  </url>')
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')


@seo_bp.get('/robots.txt')
def robots_txt():
    body = f"User-agent: *\nAllow: /\nSitemap: {request.url_root}sitemap.xml\n"
    return Response(body, mimetype='text/plain')


@seo_bp.get('/<path:dynamic_path>')
def dynamic_programmatic_entry(dynamic_path: str):
    path = '/' + dynamic_path.strip('/')
    if path in {'/', '/favicon.ico'}:
        return 'Not found', 404

    entry = ProgrammaticService.get_published_index().get(path)
    if not entry:
        return 'Page not found', 404

    return render_template('programmatic_entry.html', entry=entry)
