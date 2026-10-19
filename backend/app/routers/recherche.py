from typing import Optional

import pymysql
from fastapi import APIRouter, Depends, Query

from ..database import get_conn
from ..deps import require_roles
from ..schemas import DocumentListeOut, RechercheOut
from ..validation import mots_cles_en_liste, valider_type_document

router = APIRouter(prefix="/documents", tags=["Recherche et consultation (étudiant)"])

MAX_MOTS = 8                 # nombre maximal de mots pris en compte dans « q »
LONGUEUR_EXTRAIT = 200       # taille de l'extrait du résumé dans les résultats
COLONNES_TEXTE_LIBRE = ("d.titre", "d.auteur", "d.encadrant", "d.discipline", "d.mots_cles", "d.resume")


def _echapper_like(texte: str) -> str:
    """Empêche % et _ saisis par l'utilisateur d'agir comme des jokers SQL."""
    return texte.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contient(texte: str) -> str:
    return f"%{_echapper_like(texte.strip())}%"


def _extrait(resume: Optional[str]) -> Optional[str]:
    if not resume:
        return None
    resume = " ".join(resume.split())
    if len(resume) <= LONGUEUR_EXTRAIT:
        return resume
    return resume[:LONGUEUR_EXTRAIT].rstrip() + "…"


@router.get("/recherche", response_model=RechercheOut)
def rechercher(
    q: Optional[str] = Query(None, description="Texte libre : chaque mot est cherché dans le titre, l'auteur, "
                                               "l'encadrant, la discipline, les mots-clés et le résumé"),
    titre: Optional[str] = Query(None, description="Le titre contient ce texte"),
    auteur: Optional[str] = Query(None, description="L'auteur contient ce texte"),
    mot_cle: Optional[str] = Query(None, description="Mot-clé exact (ex. « agriculture »)"),
    annee: Optional[int] = Query(None, description="Année du document"),
    id_ufr: Optional[int] = Query(None, description="Numéro de l'UFR (voir GET /ufr)"),
    discipline: Optional[str] = Query(None, description="La discipline contient ce texte"),
    type_document: Optional[str] = Query(None, alias="type", description="THESE ou MEMOIRE"),
    telechargeable: bool = Query(False, description="true = uniquement les documents dont le PDF est téléchargeable"),
    page: int = Query(1, ge=1),
    taille: int = Query(10, ge=1, le=50, description="Résultats par page (50 maximum)"),
    user: dict = Depends(require_roles("ETUDIANT")),
    conn=Depends(get_conn),
):
    """Recherche multi-critères (tous les critères fournis se combinent).

    Règle 3 : les documents RESTREINT (embargo) n'apparaissent jamais dans les résultats d'un étudiant.
    La recherche ignore les majuscules et les accents (« memoire » trouve « Mémoire »).
    """
    conditions = ["d.niveau_acces <> 'RESTREINT'"]
    params: list = []
    criteres = []  # description lisible, enregistrée pour les statistiques (étape 4)

    if q and q.strip():
        for mot in q.split()[:MAX_MOTS]:
            conditions.append("(" + " OR ".join(f"{col} LIKE %s" for col in COLONNES_TEXTE_LIBRE) + ")")
            params += [_contient(mot)] * len(COLONNES_TEXTE_LIBRE)
        criteres.append(f"q={q.strip()}")
    if titre and titre.strip():
        conditions.append("d.titre LIKE %s")
        params.append(_contient(titre))
        criteres.append(f"titre={titre.strip()}")
    if auteur and auteur.strip():
        conditions.append("d.auteur LIKE %s")
        params.append(_contient(auteur))
        criteres.append(f"auteur={auteur.strip()}")
    if mot_cle and mot_cle.strip():
        # Les mots-clés sont stockés « a, b, c » : on cherche le mot entier, pas un morceau de mot.
        conditions.append("CONCAT(', ', d.mots_cles, ', ') LIKE %s")
        params.append(f"%, {_echapper_like(mot_cle.strip())}, %")
        criteres.append(f"mot_cle={mot_cle.strip()}")
    if annee is not None:
        conditions.append("d.annee = %s")
        params.append(annee)
        criteres.append(f"annee={annee}")
    if id_ufr is not None:
        conditions.append("d.id_ufr = %s")
        params.append(id_ufr)
        criteres.append(f"id_ufr={id_ufr}")
    if discipline and discipline.strip():
        conditions.append("d.discipline LIKE %s")
        params.append(_contient(discipline))
        criteres.append(f"discipline={discipline.strip()}")
    if type_document is not None:
        type_valide = valider_type_document(type_document)
        conditions.append("d.type = %s")
        params.append(type_valide)
        criteres.append(f"type={type_valide}")
    if telechargeable:
        conditions.append("d.niveau_acces = 'TELECHARGEABLE' AND d.chemin_pdf IS NOT NULL")
        criteres.append("telechargeable=oui")

    where = " WHERE " + " AND ".join(conditions)
    depuis = " FROM documents d JOIN ufr f ON f.id_ufr = d.id_ufr"

    total = conn.execute("SELECT COUNT(*) AS n" + depuis + where, params).fetchone()["n"]
    lignes = conn.execute(
        "SELECT d.id_document, d.titre, d.auteur, d.encadrant, d.annee, d.type, d.id_ufr, "
        "f.nom AS ufr_nom, d.discipline, d.resume, d.mots_cles, d.chemin_pdf, d.niveau_acces"
        + depuis + where
        + " ORDER BY d.annee DESC, d.titre, d.id_document LIMIT %s OFFSET %s",
        [*params, taille, (page - 1) * taille],
    ).fetchall()

    if criteres:
        try:  # le journal des recherches ne doit jamais empêcher la recherche elle-même
            conn.execute(
                "INSERT INTO recherches (id_utilisateur, requete, nb_resultats) VALUES (%s, %s, %s)",
                (user["id_utilisateur"], " | ".join(criteres)[:1000], total),
            )
            conn.commit()
        except pymysql.MySQLError:
            conn.rollback()

    return RechercheOut(
        total=total,
        page=page,
        taille=taille,
        resultats=[
            DocumentListeOut(
                id_document=d["id_document"],
                titre=d["titre"],
                auteur=d["auteur"],
                encadrant=d["encadrant"],
                annee=d["annee"],
                type=d["type"],
                id_ufr=d["id_ufr"],
                ufr_nom=d["ufr_nom"],
                discipline=d["discipline"],
                mots_cles=mots_cles_en_liste(d["mots_cles"]),
                niveau_acces=d["niveau_acces"],
                telechargeable=d["niveau_acces"] == "TELECHARGEABLE" and bool(d["chemin_pdf"]),
                extrait=_extrait(d["resume"]),
            )
            for d in lignes
        ],
    )
