import hashlib
import hmac
import secrets

KEY_PREFIX = "tfsk_"


def generate_api_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(raw_key: str, expected_hash: str) -> bool:
    candidate = hash_api_key(raw_key)
    return hmac.compare_digest(candidate, expected_hash)