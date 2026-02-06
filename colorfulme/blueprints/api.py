from __future__ import annotations

import base64
from datetime import timedelta
from pathlib import Path

from flask import Blueprint, jsonify, redirect, request, send_file
from flask_login import current_user

from extensions import db
from models import ApiKey, ApiUsageEvent, GeneratedAsset, GenerationJob
from colorfulme.services.credits_service import ensure_wallet_for_user, get_active_plan
from colorfulme.services.generation_service import GenerationService
from colorfulme.services.storage_service import StorageService
from colorfulme.utils.security import generate_api_token, hash_token, utcnow


api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


def _bearer_token() -> str | None:
    header = (request.headers.get('Authorization') or '').strip()
    if not header.lower().startswith('bearer '):
        return None
    token = header.split(' ', 1)[1].strip()
    return token or None


def _authenticate(require_user: bool = False):
    if current_user.is_authenticated:
        return current_user, None, None

    token = _bearer_token()
    if not token:
        if require_user:
            return None, None, (jsonify({'error': 'Authentication required'}), 401)
        return None, None, None

    key_hash = hash_token(token)
    api_key = ApiKey.query.filter_by(key_hash=key_hash, is_active=True).first()
    if not api_key:
        return None, None, (jsonify({'error': 'Invalid API key'}), 401)

    user = api_key.user
    if user is None:
        return None, None, (jsonify({'error': 'API key has no user'}), 401)

    plan = get_active_plan(user)
    rpm_limit = api_key.plan_rpm_override or plan.api_rpm
    window_start = utcnow() - timedelta(minutes=1)
    request_count = (
        ApiUsageEvent.query.filter_by(api_key_id=api_key.id)
        .filter(ApiUsageEvent.created_at >= window_start)
        .count()
    )
    if request_count >= rpm_limit:
        return None, None, (jsonify({'error': 'Rate limit exceeded'}), 429)

    api_key.last_used_at = utcnow()
    db.session.commit()
    return user, api_key, None


def _record_usage(*, user, api_key, status_code: int, credits_used: int = 0):
    event = ApiUsageEvent(
        api_key_id=api_key.id if api_key else None,
        user_id=user.id if user else None,
        endpoint=request.path,
        method=request.method,
        status_code=status_code,
        credits_used=credits_used,
    )
    db.session.add(event)
    db.session.commit()


def _decode_source_image(payload) -> bytes | None:
    if request.files and request.files.get('source_image'):
        data = request.files['source_image'].read()
        return data or None

    source_b64 = (payload or {}).get('source_image_base64')
    if not source_b64:
        return None

    # Support raw base64 and data URLs.
    if ',' in source_b64 and source_b64.startswith('data:'):
        source_b64 = source_b64.split(',', 1)[1]

    return base64.b64decode(source_b64)


def _serialize_job(job: GenerationJob):
    asset = job.assets[-1] if job.assets else None
    return {
        'job_id': job.id,
        'status': job.status,
        'mode': job.mode,
        'prompt': job.prompt,
        'style': job.style,
        'aspect_ratio': job.aspect_ratio,
        'difficulty': job.difficulty,
        'error_message': job.error_message,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'asset': (
            {
                'asset_id': asset.id,
                'png_url': asset.png_url,
                'pdf_url': asset.pdf_url,
                'width': asset.width,
                'height': asset.height,
            }
            if asset
            else None
        ),
    }


def _handle_generation(mode: str):
    user, api_key, error = _authenticate(require_user=True)
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    source_image = _decode_source_image(payload)

    service = GenerationService()
    result = service.create_and_process(
        user=user,
        mode=mode,
        prompt=(payload.get('prompt') or '').strip(),
        style=(payload.get('style') or '').strip() or None,
        aspect_ratio=(payload.get('aspect_ratio') or '1:1').strip(),
        difficulty=(payload.get('difficulty') or 'standard').strip(),
        source_image_bytes=source_image,
    )

    status_code = 200
    if result.job.status in {'failed', 'blocked'}:
        status_code = 422

    _record_usage(user=user, api_key=api_key, status_code=status_code, credits_used=result.credits_used)

    return (
        jsonify(
            {
                'job_id': result.job.id,
                'status': result.job.status,
                'credits_used': result.credits_used,
                'job': _serialize_job(result.job),
            }
        ),
        status_code,
    )


@api_bp.post('/generations/text')
def generate_text():
    return _handle_generation('text')


@api_bp.post('/generations/photo')
def generate_photo():
    return _handle_generation('photo')


@api_bp.post('/generations/recolor')
def generate_recolor():
    return _handle_generation('recolor')


@api_bp.get('/jobs/<job_id>')
def get_job(job_id: str):
    user, api_key, error = _authenticate(require_user=True)
    if error:
        return error

    job = GenerationJob.query.filter_by(id=job_id, user_id=user.id).first()
    if not job:
        _record_usage(user=user, api_key=api_key, status_code=404)
        return jsonify({'error': 'Job not found'}), 404

    _record_usage(user=user, api_key=api_key, status_code=200)
    return jsonify({'job': _serialize_job(job)})


@api_bp.get('/assets/<asset_id>/download')
def download_asset(asset_id: str):
    user, api_key, error = _authenticate(require_user=True)
    if error:
        return error

    fmt = (request.args.get('format') or 'png').lower()
    if fmt not in {'png', 'pdf'}:
        return jsonify({'error': 'Invalid format. Use png or pdf'}), 400

    asset = GeneratedAsset.query.filter_by(id=asset_id, user_id=user.id).first()
    if not asset:
        _record_usage(user=user, api_key=api_key, status_code=404)
        return jsonify({'error': 'Asset not found'}), 404

    key = asset.png_key if fmt == 'png' else asset.pdf_key
    mime = 'image/png' if fmt == 'png' else 'application/pdf'

    storage = StorageService()
    if storage.uses_s3:
        _record_usage(user=user, api_key=api_key, status_code=302)
        return redirect(storage.get_download_url(key))

    path = storage.absolute_local_path(key)
    if not Path(path).exists():
        _record_usage(user=user, api_key=api_key, status_code=404)
        return jsonify({'error': 'Asset file not found'}), 404

    _record_usage(user=user, api_key=api_key, status_code=200)
    return send_file(path, mimetype=mime, as_attachment=True, download_name=f'{asset_id}.{fmt}')


@api_bp.get('/me')
def me():
    user, api_key, error = _authenticate(require_user=False)
    if error:
        return error

    if not user:
        return jsonify({'authenticated': False})

    wallet = ensure_wallet_for_user(user)
    plan = get_active_plan(user)
    _record_usage(user=user, api_key=api_key, status_code=200)

    return jsonify(
        {
            'authenticated': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'plan_code': plan.code,
                'credits': wallet.balance,
            },
        }
    )


@api_bp.get('/me/credits')
def my_credits():
    user, api_key, error = _authenticate(require_user=True)
    if error:
        return error

    wallet = ensure_wallet_for_user(user)
    plan = get_active_plan(user)
    _record_usage(user=user, api_key=api_key, status_code=200)

    return jsonify(
        {
            'credits': wallet.balance,
            'plan_code': plan.code,
            'api_rpm': plan.api_rpm,
            'cycle_reset_at': wallet.cycle_reset_at.isoformat() if wallet.cycle_reset_at else None,
        }
    )


@api_bp.post('/developer/keys')
def create_api_key():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or 'Default Key').strip()[:80]

    token = generate_api_token('cmk')
    api_key = ApiKey(
        user_id=current_user.id,
        name=name,
        key_prefix=token[:12],
        key_hash=hash_token(token),
        is_active=True,
    )
    db.session.add(api_key)
    db.session.commit()

    return jsonify(
        {
            'success': True,
            'api_key': token,
            'key_id': api_key.id,
            'name': api_key.name,
            'key_prefix': api_key.key_prefix,
        }
    )


@api_bp.get('/developer/keys')
def list_api_keys():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    return jsonify(
        {
            'keys': [
                {
                    'id': key.id,
                    'name': key.name,
                    'prefix': key.key_prefix,
                    'is_active': key.is_active,
                    'created_at': key.created_at.isoformat() if key.created_at else None,
                    'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                }
                for key in keys
            ]
        }
    )


@api_bp.delete('/developer/keys/<int:key_id>')
def revoke_api_key(key_id: int):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
    if not key:
        return jsonify({'error': 'API key not found'}), 404

    key.is_active = False
    key.revoked_at = utcnow()
    db.session.commit()
    return jsonify({'success': True})
