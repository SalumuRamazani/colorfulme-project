from __future__ import annotations

from datetime import timedelta
import json
import logging
import re
import secrets
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app, session, url_for

from extensions import db
from models import AuthIdentity, EmailOtpCode, User
from colorfulme.services.credits_service import ensure_free_subscription, ensure_wallet_for_user
from colorfulme.utils.security import generate_otp_code, hash_otp, utcnow


EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class AuthService:
    def __init__(self):
        self.secret = current_app.config['SECRET_KEY']

    def send_email_otp(self, email: str, ip_address: str | None = None) -> Optional[str]:
        normalized = self._normalize_email(email)
        if not EMAIL_RE.match(normalized):
            raise ValueError('Invalid email address')

        code = generate_otp_code(6)
        code_hash = hash_otp(normalized, code, self.secret)
        now = utcnow()

        # Invalidate prior active codes for deterministic verification.
        for item in EmailOtpCode.query.filter_by(email=normalized, consumed_at=None).all():
            item.consumed_at = now

        otp_row = EmailOtpCode(
            email=normalized,
            code_hash=code_hash,
            purpose='login',
            expires_at=now + timedelta(minutes=10),
            ip_address=ip_address,
        )
        db.session.add(otp_row)
        db.session.commit()

        self._deliver_otp(normalized, code)

        if current_app.config.get('TESTING'):
            return code
        return None

    def verify_email_otp(self, email: str, code: str, display_name: str | None = None) -> User:
        normalized = self._normalize_email(email)
        now = utcnow()

        otp_row = (
            EmailOtpCode.query.filter_by(email=normalized, consumed_at=None)
            .order_by(EmailOtpCode.created_at.desc())
            .first()
        )
        if otp_row is None:
            raise ValueError('No active code found. Request a new code.')

        if otp_row.expires_at <= now:
            raise ValueError('Code expired. Request a new code.')

        otp_row.attempts += 1
        if otp_row.attempts > 6:
            otp_row.consumed_at = now
            db.session.commit()
            raise ValueError('Too many attempts. Request a new code.')

        expected_hash = hash_otp(normalized, code.strip(), self.secret)
        if expected_hash != otp_row.code_hash:
            db.session.commit()
            raise ValueError('Incorrect verification code')

        otp_row.consumed_at = now

        user = User.query.filter_by(email=normalized).first()
        if user is None:
            user = User(
                email=normalized,
                display_name=(display_name or normalized.split('@', 1)[0]).strip()[:120],
            )
            db.session.add(user)
            db.session.flush()

        identity = AuthIdentity.query.filter_by(provider='email', provider_user_id=normalized).first()
        if identity is None:
            identity = AuthIdentity(
                user_id=user.id,
                provider='email',
                provider_user_id=normalized,
                email=normalized,
            )
            db.session.add(identity)

        user.last_login_at = now
        db.session.commit()

        ensure_free_subscription(user)
        ensure_wallet_for_user(user)
        return user

    def build_google_redirect(self, next_url: str | None = None) -> str:
        client_id = (os_get('GOOGLE_CLIENT_ID') or '').strip()
        client_secret = (os_get('GOOGLE_CLIENT_SECRET') or '').strip()

        if not client_id or not client_secret:
            demo_email = current_app.config.get('GOOGLE_DEV_EMAIL', 'demo@colorfulme.app')
            return url_for('auth.google_callback', code='dev-demo', email=demo_email, next=next_url or '/dashboard')

        state = secrets.token_urlsafe(24)
        session['google_oauth_state'] = state

        callback_url = url_for('auth.google_callback', _external=True)
        params = {
            'client_id': client_id,
            'redirect_uri': callback_url,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent',
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    def authenticate_google_callback(self, args) -> User:
        code = (args.get('code') or '').strip()
        requested_next = args.get('next') or '/dashboard'

        if code == 'dev-demo':
            email = self._normalize_email(args.get('email') or 'demo@colorfulme.app')
            google_subject = f"dev-{email}"
            user_data = {
                'sub': google_subject,
                'email': email,
                'name': 'ColorfulMe Demo',
            }
            return self._upsert_google_user(user_data, requested_next)

        state = args.get('state')
        expected_state = session.get('google_oauth_state')
        if not state or not expected_state or state != expected_state:
            raise ValueError('Invalid OAuth state')

        client_id = (os_get('GOOGLE_CLIENT_ID') or '').strip()
        client_secret = (os_get('GOOGLE_CLIENT_SECRET') or '').strip()
        if not client_id or not client_secret:
            raise ValueError('Google OAuth is not configured')

        callback_url = url_for('auth.google_callback', _external=True)
        token_resp = self._http_json(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': callback_url,
                'grant_type': 'authorization_code',
            },
            method='POST',
        )

        access_token = token_resp.get('access_token')
        if not access_token:
            raise ValueError('Missing Google access token')

        userinfo = self._http_json(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={
                'Authorization': f'Bearer {access_token}',
            },
            method='GET',
        )

        if not userinfo.get('email'):
            raise ValueError('Google account did not provide an email')

        return self._upsert_google_user(userinfo, requested_next)

    def _upsert_google_user(self, userinfo: dict, _next: str) -> User:
        email = self._normalize_email(userinfo.get('email'))
        provider_user_id = str(userinfo.get('sub') or email)
        display_name = (userinfo.get('name') or email.split('@', 1)[0]).strip()[:120]

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, display_name=display_name)
            db.session.add(user)
            db.session.flush()
        elif not user.display_name:
            user.display_name = display_name

        identity = AuthIdentity.query.filter_by(provider='google', provider_user_id=provider_user_id).first()
        if identity is None:
            identity = AuthIdentity(
                user_id=user.id,
                provider='google',
                provider_user_id=provider_user_id,
                email=email,
            )
            db.session.add(identity)

        user.last_login_at = utcnow()
        db.session.commit()

        ensure_free_subscription(user)
        ensure_wallet_for_user(user)
        return user

    @staticmethod
    def _normalize_email(email: str) -> str:
        return (email or '').strip().lower()

    def _deliver_otp(self, email: str, code: str) -> None:
        resend_api_key = os_get('RESEND_API_KEY')
        sender = os_get('RESEND_FROM_EMAIL')
        if not resend_api_key or not sender:
            logging.info('OTP for %s is %s (email provider not configured, logged for local development)', email, code)
            return

        payload = {
            'from': sender,
            'to': [email],
            'subject': 'Your ColorfulMe login code',
            'html': (
                '<p>Your ColorfulMe verification code is:</p>'
                f'<p style="font-size:24px;font-weight:700;letter-spacing:2px;">{code}</p>'
                '<p>This code expires in 10 minutes.</p>'
            ),
        }

        try:
            self._http_json(
                'https://api.resend.com/emails',
                data=payload,
                headers={
                    'Authorization': f'Bearer {resend_api_key}',
                    'Content-Type': 'application/json',
                },
                method='POST',
                json_encoded=True,
            )
        except Exception as exc:
            logging.warning('Failed to send OTP email via Resend: %s', exc)

    @staticmethod
    def _http_json(url: str, *, data=None, headers=None, method='GET', json_encoded=False):
        body = None
        headers = headers or {}
        method = method.upper()

        if data is not None:
            if json_encoded:
                body = json.dumps(data).encode('utf-8')
            else:
                body = urlencode(data).encode('utf-8')
                headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')

        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=20) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw)


def os_get(name: str) -> str:
    return current_app.config.get(name) or current_app.config.get(name.lower()) or __import__('os').getenv(name, '')
