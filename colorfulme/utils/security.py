from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime


def utcnow() -> datetime:
    return datetime.utcnow()


def generate_api_token(prefix: str = 'cm') -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def generate_otp_code(length: int = 6) -> str:
    upper = 10 ** length
    lower = 10 ** (length - 1)
    return str(secrets.randbelow(upper - lower) + lower)


def hash_otp(email: str, code: str, secret: str) -> str:
    payload = f"{email.lower().strip()}:{code}:{secret}".encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
