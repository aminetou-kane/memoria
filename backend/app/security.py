from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings
from .exceptions import AuthentificationError


def hash_password(mot_de_passe: str) -> str:
    return bcrypt.hashpw(mot_de_passe.encode(), bcrypt.gensalt()).decode()


def verify_password(mot_de_passe: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(mot_de_passe.encode(), hash_.encode())
    except ValueError:
        return False


def create_token(id_utilisateur: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(id_utilisateur), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise AuthentificationError("Session invalide ou expirée.")
