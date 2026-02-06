from __future__ import annotations

import os
from typing import Dict, Any

from flask import current_app

from programmatic_content import build_published_route_index, load_manifest


_cache: dict[str, Any] = {
    'path': None,
    'mtime': None,
    'manifest': None,
    'index': None,
}


class ProgrammaticService:
    @staticmethod
    def _manifest_path() -> str:
        return current_app.config['PROGRAMMATIC_CONTENT_MANIFEST']

    @classmethod
    def _load_if_needed(cls) -> None:
        path = cls._manifest_path()
        mtime = os.path.getmtime(path) if os.path.exists(path) else None

        if _cache['path'] == path and _cache['mtime'] == mtime and _cache['manifest'] is not None:
            return

        manifest = load_manifest(path)
        _cache['path'] = path
        _cache['mtime'] = mtime
        _cache['manifest'] = manifest
        _cache['index'] = build_published_route_index(manifest)

    @classmethod
    def get_manifest(cls) -> Dict[str, Any]:
        cls._load_if_needed()
        return _cache['manifest'] or {'entries': [], 'counts': {'total': 0, 'pages': 0, 'tools': 0, 'library': 0}}

    @classmethod
    def get_published_index(cls) -> Dict[str, Dict[str, Any]]:
        cls._load_if_needed()
        return _cache['index'] or {}

    @classmethod
    def get_entries(cls):
        manifest = cls.get_manifest()
        entries = manifest.get('entries', [])
        if not isinstance(entries, list):
            return []
        return entries

    @classmethod
    def get_entries_by_type(cls, entry_type: str):
        return [entry for entry in cls.get_entries() if entry.get('entry_type') == entry_type]
