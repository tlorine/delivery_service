"""Server-side validation of Telegram Mini App initData.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token); hash = HMAC_SHA256(secret_key, data_check_string)
initDataUnsafe on the client is never trusted.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from app.core.errors import Unauthorized


@dataclass(frozen=True, slots=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None


@dataclass(frozen=True, slots=True)
class VerifiedInitData:
    user: TelegramUser
    auth_date: datetime
    query_id: str | None
    start_param: str | None


def _fail(detail: str) -> Unauthorized:
    return Unauthorized(detail, code="invalid_init_data")


def verify_init_data(init_data: str, bot_token: str, now: datetime, max_age: timedelta) -> VerifiedInitData:
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise _fail("malformed initData") from None
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise _fail("duplicate keys")
    received = fields.pop("hash", None)
    if not received:
        raise _fail("hash is missing")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise _fail("bad signature")

    try:
        auth_date = datetime.fromtimestamp(int(fields["auth_date"]), UTC)
    except (KeyError, ValueError):
        raise _fail("auth_date is missing") from None
    if auth_date > now + timedelta(minutes=5) or now - auth_date > max_age:
        raise _fail("initData is expired")
    try:
        raw_user = json.loads(fields["user"])
        user = TelegramUser(
            id=int(raw_user["id"]),
            first_name=str(raw_user.get("first_name", "")),
            last_name=raw_user.get("last_name"),
            username=raw_user.get("username"),
            language_code=raw_user.get("language_code"),
        )
    except (KeyError, ValueError, TypeError):
        raise _fail("user is missing") from None
    return VerifiedInitData(user, auth_date, fields.get("query_id"), fields.get("start_param"))
