from typing import List

import pymysql
from fastapi import APIRouter, Depends

from ..database import est_doublon, get_conn
from ..deps import current_user, require_roles
from ..exceptions import DoublonError, RegleMetierError, UfrIntrouvableError
from ..schemas import UfrIn, UfrOut
from ..validation import exiger_texte

router = APIRouter(prefix="/ufr", tags=["UFR / centres de documentation"])


def _get_ufr(conn, id_ufr: int) -> dict:
    row = conn.execute("SELECT id_ufr, nom FROM ufr WHERE id_ufr = %s", (id_ufr,)).fetchone()
    if row is None:
        raise UfrIntrouvableError(f"UFR {id_ufr} introuvable.")
    return row


def _verifier_nom_libre(conn, nom: str, exclude_id=None) -> None:
    row = conn.execute(
        "SELECT 1 FROM ufr WHERE lower(nom) = lower(%s) AND NOT (id_ufr <=> %s)",
        (nom, exclude_id),
    ).fetchone()
    if row:
        raise DoublonError(f"Une UFR nommée '{nom}' existe déjà.")


@router.get("", response_model=List[UfrOut], dependencies=[Depends(current_user)])
def lister(conn=Depends(get_conn)):
    return conn.execute("SELECT id_ufr, nom FROM ufr ORDER BY nom").fetchall()


@router.post("", response_model=UfrOut, status_code=201, dependencies=[Depends(require_roles("ADMIN"))])
def creer(data: UfrIn, conn=Depends(get_conn)):
    nom = exiger_texte(data.nom, "nom")
    _verifier_nom_libre(conn, nom)
    try:
        curseur = conn.execute("INSERT INTO ufr (nom) VALUES (%s)", (nom,))
    except pymysql.err.IntegrityError as erreur:
        conn.rollback()
        if est_doublon(erreur):
            raise DoublonError(f"Une UFR nommée '{nom}' existe déjà.")
        raise
    conn.commit()
    return {"id_ufr": curseur.lastrowid, "nom": nom}


@router.put("/{id_ufr}", response_model=UfrOut, dependencies=[Depends(require_roles("ADMIN"))])
def modifier(id_ufr: int, data: UfrIn, conn=Depends(get_conn)):
    _get_ufr(conn, id_ufr)
    nom = exiger_texte(data.nom, "nom")
    _verifier_nom_libre(conn, nom, exclude_id=id_ufr)
    conn.execute("UPDATE ufr SET nom = %s WHERE id_ufr = %s", (nom, id_ufr))
    conn.commit()
    return _get_ufr(conn, id_ufr)


@router.delete("/{id_ufr}", status_code=204, dependencies=[Depends(require_roles("ADMIN"))])
def supprimer(id_ufr: int, conn=Depends(get_conn)):
    _get_ufr(conn, id_ufr)
    utilisee = conn.execute(
        "SELECT (SELECT count(*) FROM utilisateurs WHERE id_ufr = %s) "
        "     + (SELECT count(*) FROM documents WHERE id_ufr = %s) AS n",
        (id_ufr, id_ufr),
    ).fetchone()["n"]
    if utilisee:
        raise RegleMetierError(
            "Impossible de supprimer cette UFR : des gestionnaires ou des documents y sont rattachés."
        )
    conn.execute("DELETE FROM ufr WHERE id_ufr = %s", (id_ufr,))
    conn.commit()
