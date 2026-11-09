import hashlib
import hmac
import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

_hasher = PasswordHasher()  # Argon2id with library defaults (RFC 9106 recommended profile)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    """Bearer tokens are stored as SHA-256: high-entropy secrets need no slow hash."""
    return hashlib.sha256(token.encode()).digest()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def order_access_token(secret: str, order_id: uuid.UUID) -> str:
    """Deterministic so an idempotent retry can return the same token without storing it in clear."""
    digest = hmac.new(secret.encode(), b"order:" + order_id.bytes, hashlib.sha256).digest()
    return order_id.hex + "." + digest[:18].hex()


class SecretBox:
    """Symmetric encryption for third-party secrets kept in the DB (bot tokens, payment keys)."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode()
