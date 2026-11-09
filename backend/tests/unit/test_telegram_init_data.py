import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from app.core.errors import Unauthorized
from app.modules.telegram.init_data import verify_init_data

TOKEN = "123456:CAFE-A-TOKEN"
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
MAX_AGE = timedelta(hours=24)


def sign(fields: dict[str, str], token: str = TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


def fields(auth_date: datetime = NOW, **extra: str) -> dict[str, str]:
    return {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": "AAH",
        "user": json.dumps({"id": 42, "first_name": "Анна", "username": "anna", "language_code": "ru"}),
        **extra,
    }


def test_valid_init_data() -> None:
    data = verify_init_data(sign(fields(start_param="promo")), TOKEN, NOW, MAX_AGE)
    assert data.user.id == 42
    assert data.user.first_name == "Анна"
    assert data.start_param == "promo"


def test_signature_from_another_bot_is_rejected() -> None:
    with pytest.raises(Unauthorized):
        verify_init_data(sign(fields(), "999:OTHER-CAFE"), TOKEN, NOW, MAX_AGE)


def test_tampered_user_is_rejected() -> None:
    raw = sign(fields())
    tampered = raw.replace("%22id%22%3A+42", "%22id%22%3A+43")
    assert tampered != raw
    with pytest.raises(Unauthorized):
        verify_init_data(tampered, TOKEN, NOW, MAX_AGE)


@pytest.mark.parametrize("auth_date", [NOW - timedelta(hours=25), NOW + timedelta(hours=1)])
def test_stale_or_future_auth_date_is_rejected(auth_date: datetime) -> None:
    with pytest.raises(Unauthorized):
        verify_init_data(sign(fields(auth_date)), TOKEN, NOW, MAX_AGE)


@pytest.mark.parametrize("raw", ["", "user=x", "auth_date=1&hash=abc", "a=1&a=2&hash=x", "%%%"])
def test_malformed_input(raw: str) -> None:
    with pytest.raises(Unauthorized):
        verify_init_data(raw, TOKEN, NOW, MAX_AGE)
