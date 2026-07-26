import itsdangerous
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlmodel import Session

from app.config import settings
from app.models.user import User

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600

_password_hasher = PasswordHasher()


class SessionSecretNotConfiguredError(Exception):
    pass


def _serializer() -> itsdangerous.URLSafeTimedSerializer:
    key = settings.session_secret_key
    if not key:
        raise SessionSecretNotConfiguredError("SESSION_SECRET_KEY не задан")
    return itsdangerous.URLSafeTimedSerializer(key)


def create_session_cookie(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "v": user.session_version})


def verify_session_cookie(token: str, session: Session) -> User | None:
    """Проверяет подпись/срок cookie и сверяет session_version с текущим —
    сброс пароля (`reset-admin-password`) инкрементирует version и тем
    самым инвалидирует все ранее выданные cookie."""
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except itsdangerous.BadSignature:
        return None
    user = session.get(User, payload.get("uid"))
    if user is None or user.session_version != payload.get("v"):
        return None
    return user


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerificationError:
        return False
