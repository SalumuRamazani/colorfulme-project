from __future__ import annotations

from flask import Blueprint, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from colorfulme.services.auth_service import AuthService


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.get('/google/start')
def google_start():
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))

    next_url = request.args.get('next', '/dashboard')
    session['auth_next_url'] = next_url
    redirect_url = AuthService().build_google_redirect(next_url)
    return redirect(redirect_url)


@auth_bp.get('/google/callback')
def google_callback():
    service = AuthService()
    try:
        user = service.authenticate_google_callback(request.args)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    login_user(user, remember=True)
    target = session.pop('auth_next_url', None) or request.args.get('next') or url_for('web.dashboard')
    return redirect(target)


@auth_bp.post('/email/send-code')
def send_email_code():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email', '')

    try:
        code = AuthService().send_email_otp(email=email, ip_address=request.remote_addr)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    response = {'success': True, 'message': 'Verification code sent'}
    if code:
        response['code'] = code
    return jsonify(response)


@auth_bp.post('/email/verify-code')
def verify_email_code():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email', '')
    code = payload.get('code', '')
    display_name = payload.get('display_name')

    try:
        user = AuthService().verify_email_otp(email=email, code=code, display_name=display_name)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    login_user(user, remember=True)
    return jsonify({'success': True, 'user': {'id': user.id, 'email': user.email, 'display_name': user.display_name}})


@auth_bp.post('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})
