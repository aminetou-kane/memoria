from typing import List, Optional

import pymysql
from fastapi import APIRouter, Depends, Query

from ..database import est_doublon, get_conn
from ..deps import require_roles
from ..exceptions import (
    AccesRefuseError,
    ChampInvalideError,
    DoublonError,
    UfrIntrouvableError,
    UtilisateurIntrouvableError,
)
from ..schemas import EtudiantIn, GestionnaireIn, UtilisateurOut, UtilisateurUpdate
from ..security import hash_password
from ..validation import exiger_texte, valider_email_ugb, valider_mot_de_passe

# Tout ce module est réservé à l'administrateur.
router = APIRouter(
    prefix="/users",
    tags=["Gestion des utilisateurs (admin)"],
    dependencies=[Depends(require_roles("ADMIN"))],
)

SELECT_UTILISATEUR = """
    SELECT u.id_utilisateur, u.nom, u.prenom, u.email, u.role, u.id_ufr,
           f.nom AS ufr_nom, u.code_etudiant
    FROM utilisateurs u
    LEFT JOIN ufr f ON f.id_ufr = u.id_ufr
"""


def _lire(conn, id_utilisateur: int) -> dict:
    row = conn.execute(
        SELECT_UTILISATEUR + " WHERE u.id_utilisateur = %s", (id_utilisateur,)
    ).fetchone()
    if row is None:
        raise UtilisateurIntrouvableError(f"Utilisateur {id_utilisateur} introuvable.")
    return row


def _verifier_ufr(conn, id_ufr: int) -> None:
    if conn.execute("SELECT 1 FROM ufr WHERE id_ufr = %s", (id_ufr,)).fetchone() is None:
        raise UfrIntrouvableError(f"UFR {id_ufr} introuvable.")


def _verifier_unicite(conn, email=None, code_etudiant=None, exclude_id=None) -> None:
    if email and conn.execute(
        "SELECT 1 FROM utilisateurs WHERE email = %s AND NOT (id_utilisateur <=> %s)",
        (email, exclude_id),
    ).fetchone():
        raise DoublonError(f"L'email '{email}' est déjà utilisé.")
    if code_etudiant and conn.execute(
        "SELECT 1 FROM utilisateurs WHERE code_etudiant = %s AND NOT (id_utilisateur <=> %s)",
        (code_etudiant, exclude_id),
    ).fetchone():
        raise DoublonError(f"Le code étudiant '{code_etudiant}' est déjà utilisé.")


def _inserer(conn, nom, prenom, email, role, id_ufr=None, code_etudiant=None, mdp_hash=None) -> dict:
    try:
        curseur = conn.execute(
            "INSERT INTO utilisateurs (nom, prenom, email, role, id_ufr, code_etudiant, mot_de_passe_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (nom, prenom, email, role, id_ufr, code_etudiant, mdp_hash),
        )
    except pymysql.err.IntegrityError as erreur:
        conn.rollback()
        if est_doublon(erreur):
            raise DoublonError("Cet email ou ce code étudiant est déjà utilisé.")
        raise
    conn.commit()
    return _lire(conn, curseur.lastrowid)


@router.get("", response_model=List[UtilisateurOut])
def lister(
    q: Optional[str] = Query(None, description="Recherche par nom, prénom ou email"),
    role: Optional[str] = Query(None, description="ADMIN, GESTIONNAIRE ou ETUDIANT"),
    conn=Depends(get_conn),
):
    conditions, params = [], []
    if q and q.strip():
        motif = f"%{q.strip()}%"
        conditions.append("(u.nom LIKE %s OR u.prenom LIKE %s OR u.email LIKE %s)")
        params += [motif, motif, motif]
    if role:
        role = role.upper()
        if role not in ("ADMIN", "GESTIONNAIRE", "ETUDIANT"):
            raise ChampInvalideError("Rôle inconnu (ADMIN, GESTIONNAIRE ou ETUDIANT).")
        conditions.append("u.role = %s")
        params.append(role)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    return conn.execute(
        SELECT_UTILISATEUR + where + " ORDER BY u.nom, u.prenom", params
    ).fetchall()


@router.get("/{id_utilisateur}", response_model=UtilisateurOut)
def detail(id_utilisateur: int, conn=Depends(get_conn)):
    return _lire(conn, id_utilisateur)


@router.post("/gestionnaires", response_model=UtilisateurOut, status_code=201)
def creer_gestionnaire(data: GestionnaireIn, conn=Depends(get_conn)):
    nom = exiger_texte(data.nom, "nom", 80)
    prenom = exiger_texte(data.prenom, "prenom", 80)
    email = valider_email_ugb(data.email)
    mdp = valider_mot_de_passe(data.mot_de_passe)
    _verifier_ufr(conn, data.id_ufr)
    _verifier_unicite(conn, email=email)
    return _inserer(
        conn, nom, prenom, email, "GESTIONNAIRE", id_ufr=data.id_ufr, mdp_hash=hash_password(mdp)
    )


@router.post("/etudiants", response_model=UtilisateurOut, status_code=201)
def creer_etudiant(data: EtudiantIn, conn=Depends(get_conn)):
    nom = exiger_texte(data.nom, "nom", 80)
    prenom = exiger_texte(data.prenom, "prenom", 80)
    email = valider_email_ugb(data.email)
    code = exiger_texte(data.code_etudiant, "code_etudiant", 30)
    _verifier_unicite(conn, email=email, code_etudiant=code)
    return _inserer(conn, nom, prenom, email, "ETUDIANT", code_etudiant=code)


@router.put("/{id_utilisateur}", response_model=UtilisateurOut)
def modifier(id_utilisateur: int, data: UtilisateurUpdate, conn=Depends(get_conn)):
    """Modifie un gestionnaire ou un étudiant. Pour affecter un gestionnaire à une UFR : id_ufr."""
    user = _lire(conn, id_utilisateur)
    if user["role"] == "ADMIN":
        raise AccesRefuseError("Le compte administrateur ne peut pas être modifié ici.")

    champs = {}
    if data.nom is not None:
        champs["nom"] = exiger_texte(data.nom, "nom", 80)
    if data.prenom is not None:
        champs["prenom"] = exiger_texte(data.prenom, "prenom", 80)
    if data.email is not None:
        champs["email"] = valider_email_ugb(data.email)
    if data.id_ufr is not None:
        if user["role"] != "GESTIONNAIRE":
            raise ChampInvalideError("Seul un gestionnaire peut être affecté à une UFR.")
        _verifier_ufr(conn, data.id_ufr)
        champs["id_ufr"] = data.id_ufr
    if data.code_etudiant is not None:
        if user["role"] != "ETUDIANT":
            raise ChampInvalideError("Seul un étudiant possède un code étudiant.")
        champs["code_etudiant"] = exiger_texte(data.code_etudiant, "code_etudiant", 30)
    if data.mot_de_passe is not None:
        if user["role"] != "GESTIONNAIRE":
            raise ChampInvalideError("Seul un gestionnaire possède un mot de passe.")
        champs["mot_de_passe_hash"] = hash_password(valider_mot_de_passe(data.mot_de_passe))
    if not champs:
        raise ChampInvalideError("Aucune modification fournie.")

    _verifier_unicite(
        conn, email=champs.get("email"), code_etudiant=champs.get("code_etudiant"),
        exclude_id=id_utilisateur,
    )
    # Les noms de colonnes viennent du dictionnaire ci-dessus (jamais de l'utilisateur).
    assignations = ", ".join(f"{col} = %s" for col in champs)
    conn.execute(
        f"UPDATE utilisateurs SET {assignations} WHERE id_utilisateur = %s",
        [*champs.values(), id_utilisateur],
    )
    conn.commit()
    return _lire(conn, id_utilisateur)


@router.delete("/{id_utilisateur}", status_code=204)
def supprimer(id_utilisateur: int, conn=Depends(get_conn)):
    user = _lire(conn, id_utilisateur)
    if user["role"] == "ADMIN":
        raise AccesRefuseError("Le compte administrateur ne peut pas être supprimé.")
    conn.execute("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (id_utilisateur,))
    conn.commit()
