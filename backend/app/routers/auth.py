from fastapi import APIRouter, Depends

from ..database import get_conn
from ..deps import current_user
from ..exceptions import AuthentificationError
from ..schemas import LoginEtudiantIn, LoginIn, TokenOut
from ..security import create_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentification"])


def _token(user: dict) -> TokenOut:
    return TokenOut(
        access_token=create_token(user["id_utilisateur"], user["role"]),
        role=user["role"],
        nom=user["nom"],
        prenom=user["prenom"],
    )


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, conn=Depends(get_conn)):
    """Connexion des administrateurs et gestionnaires (email + mot de passe)."""
    user = conn.execute(
        "SELECT * FROM utilisateurs WHERE email = %s AND role IN ('ADMIN', 'GESTIONNAIRE')",
        (data.email.strip().lower(),),
    ).fetchone()
    if (
        user is None
        or not user["mot_de_passe_hash"]
        or not verify_password(data.mot_de_passe, user["mot_de_passe_hash"])
    ):
        raise AuthentificationError("Email ou mot de passe incorrect.")
    return _token(user)


@router.post("/login-etudiant", response_model=TokenOut)
def login_etudiant(data: LoginEtudiantIn, conn=Depends(get_conn)):
    """Connexion étudiant : prénom, nom, email UGB et code étudiant (sans mot de passe)."""
    user = conn.execute(
        "SELECT * FROM utilisateurs WHERE role = 'ETUDIANT' AND email = %s AND code_etudiant = %s",
        (data.email.strip().lower(), data.code_etudiant.strip()),
    ).fetchone()
    if (
        user is None
        or user["nom"].strip().lower() != data.nom.strip().lower()
        or user["prenom"].strip().lower() != data.prenom.strip().lower()
    ):
        raise AuthentificationError("Informations étudiant incorrectes.")
    return _token(user)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user
