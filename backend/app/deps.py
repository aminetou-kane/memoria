from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import get_conn
from .exceptions import AccesRefuseError, AuthentificationError
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer), conn=Depends(get_conn)
) -> dict:
    if creds is None:
        raise AuthentificationError("Authentification requise.")
    payload = decode_token(creds.credentials)
    user = conn.execute(
        "SELECT id_utilisateur, nom, prenom, email, role, id_ufr, code_etudiant "
        "FROM utilisateurs WHERE id_utilisateur = %s",
        (int(payload["sub"]),),
    ).fetchone()
    if user is None:
        raise AuthentificationError("Compte introuvable.")
    return user


def require_roles(*roles: str):
    def checker(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise AccesRefuseError("Vous n'avez pas les droits pour cette action.")
        return user

    return checker
