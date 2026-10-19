from typing import List

from fastapi import APIRouter, Depends

from ..database import get_conn
from ..deps import require_roles
from ..exceptions import AccesRefuseError, DocumentIntrouvableError
from ..schemas import MonTelechargementOut, TelechargementGestionOut

router = APIRouter(prefix="/telechargements", tags=["Historique des téléchargements"])


@router.get("/moi", response_model=List[MonTelechargementOut])
def mon_historique(user: dict = Depends(require_roles("ETUDIANT")), conn=Depends(get_conn)):
    """Historique personnel de l'étudiant connecté."""
    return conn.execute(
        "SELECT t.id_telechargement, t.id_document, d.titre, d.auteur, t.date_telechargement "
        "FROM telechargements t JOIN documents d ON d.id_document = t.id_document "
        "WHERE t.id_utilisateur = %s ORDER BY t.date_telechargement DESC, t.id_telechargement DESC",
        (user["id_utilisateur"],),
    ).fetchall()


SELECT_HISTORIQUE_GESTION = """
    SELECT t.id_telechargement, t.id_document, d.titre, u.id_utilisateur, u.nom, u.prenom,
           u.email, u.code_etudiant, t.date_telechargement
    FROM telechargements t
    JOIN documents d ON d.id_document = t.id_document
    JOIN utilisateurs u ON u.id_utilisateur = t.id_utilisateur
"""


@router.get("/gestion", response_model=List[TelechargementGestionOut])
def historique_de_mon_ufr(user: dict = Depends(require_roles("GESTIONNAIRE")), conn=Depends(get_conn)):
    """Tous les téléchargements des documents de l'UFR du gestionnaire."""
    return conn.execute(
        SELECT_HISTORIQUE_GESTION
        + " WHERE d.id_ufr = %s ORDER BY t.date_telechargement DESC, t.id_telechargement DESC",
        (user["id_ufr"],),
    ).fetchall()


@router.get("/document/{id_document}", response_model=List[TelechargementGestionOut])
def historique_d_un_document(
    id_document: int, user: dict = Depends(require_roles("GESTIONNAIRE")), conn=Depends(get_conn)
):
    """Historique des téléchargements d'un document de l'UFR du gestionnaire."""
    doc = conn.execute(
        "SELECT id_ufr FROM documents WHERE id_document = %s", (id_document,)
    ).fetchone()
    if doc is None:
        raise DocumentIntrouvableError(f"Document {id_document} introuvable.")
    if doc["id_ufr"] != user["id_ufr"]:
        raise AccesRefuseError("Ce document appartient à une autre UFR.")
    return conn.execute(
        SELECT_HISTORIQUE_GESTION
        + " WHERE t.id_document = %s ORDER BY t.date_telechargement DESC, t.id_telechargement DESC",
        (id_document,),
    ).fetchall()
