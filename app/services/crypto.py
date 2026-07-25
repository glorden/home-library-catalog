from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionNotConfiguredError(Exception):
    pass


def _fernet() -> Fernet:
    key = settings.settings_encryption_key
    if not key:
        raise EncryptionNotConfiguredError("SETTINGS_ENCRYPTION_KEY не задан")
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionNotConfiguredError(
            "Не удалось расшифровать сохранённый ключ — проверьте SETTINGS_ENCRYPTION_KEY"
        ) from exc
