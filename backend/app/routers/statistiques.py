"""Module Statistiques et rapports.

- L'administrateur voit tout (et peut filtrer par UFR avec ?id_ufr=).
- Le gestionnaire ne voit que les statistiques de SON UFR.
"""
import csv
import io
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..database import get_conn
from ..deps import require_roles
from ..exceptions import AccesRefuseError, ChampInvalideError, UfrIntrouvableError
from ..schemas import (
    ActiviteUfrOut,
    DocumentRestreintOut,
    RechercheSansResultatOut,
    RepartitionOut,
    StatsDocumentsOut,
    StatsGlobalesOut,
    StatsRecherchesOut,
    StatsTelechargementsOut,
    TopDocumentOut,
)

router = APIRouter(prefix="/statistiques", tags=["Statistiques et rapports"])

admin_ou_gestionnaire = require_roles("ADMIN", "GESTIONNAIRE")

NIVEAUX = ("TELECHARGEABLE", "CONSULTATION_SEULE", "RESTREINT")
ROLES = ("ADMIN", "GESTIONNAIRE", "ETUDIANT")

# Expressions SQL autorisées pour « répartition » (liste blanche : jamais de texte venant de l'utilisateur).
AXES_REPARTITION = {
    "discipline": "COALESCE(NULLIF(TRIM(d.discipline), ''), 'Non renseignée')",
    "annee": "CAST(d.annee AS CHAR)",
    "type": "d.type",
    "niveau_acces": "d.niveau_acces",
}


# ---------------------------------------------------------------- portée (qui voit quoi)
def _portee(conn, user: dict, id_ufr: Optional[int]) -> Optional[int]:
    """Renvoie l'UFR à analyser, ou None pour « tout le fonds » (administrateur uniquement)."""
    if user["role"] == "GESTIONNAIRE":
        if id_ufr is not None and id_ufr != user["id_ufr"]:
            raise AccesRefuseError("Vous ne pouvez consulter que les statistiques de votre UFR.")
        return user["id_ufr"]
    if id_ufr is not None and conn.execute("SELECT 1 FROM ufr WHERE id_ufr = %s", (id_ufr,)).fetchone() is None:
        raise UfrIntrouvableError(f"UFR {id_ufr} introuvable.")
    return id_ufr


def _filtre(portee: Optional[int]):
    """Fragment SQL « AND d.id_ufr = ? » (vide pour une portée globale)."""
    return (" AND d.id_ufr = %s", [portee]) if portee is not None else ("", [])


def _admin_seulement(user: dict) -> None:
    if user["role"] != "ADMIN":
        raise AccesRefuseError("Cette statistique est réservée à l'administrateur.")


# ---------------------------------------------------------------- chargeurs (réutilisés par l'export CSV)
def _charger_top_documents(conn, portee, limite=10) -> list:
    filtre, params = _filtre(portee)
    return conn.execute(
        "SELECT d.id_document, d.titre, d.auteur, f.nom AS ufr_nom, COUNT(t.id_telechargement) AS nb_telechargements "
        "FROM documents d JOIN ufr f ON f.id_ufr = d.id_ufr "
        "JOIN telechargements t ON t.id_document = d.id_document "
        "WHERE 1 = 1" + filtre +
        " GROUP BY d.id_document, d.titre, d.auteur, f.nom "
        "ORDER BY nb_telechargements DESC, d.titre, d.id_document LIMIT %s",
        [*params, limite],
    ).fetchall()


def _charger_activite_ufr(conn, portee, limite=None) -> list:
    where, params = ("WHERE f.id_ufr = %s", [portee]) if portee is not None else ("", [])
    return conn.execute(
        "SELECT f.id_ufr, f.nom, "
        "  (SELECT COUNT(*) FROM documents d WHERE d.id_ufr = f.id_ufr) AS nb_documents, "
        "  (SELECT COUNT(*) FROM telechargements t JOIN documents d ON d.id_document = t.id_document "
        "   WHERE d.id_ufr = f.id_ufr) AS nb_telechargements "
        f"FROM ufr f {where} ORDER BY nb_telechargements DESC, nb_documents DESC, f.nom",
        params,
    ).fetchall()


def _charger_repartition(conn, portee, axe: str) -> list:
    if axe not in AXES_REPARTITION:
        raise ChampInvalideError(f"Axe inconnu. Valeurs possibles : {', '.join(AXES_REPARTITION)}.")
    filtre, params = _filtre(portee)
    ordre = "libelle" if axe == "annee" else "nb_documents DESC, libelle"
    return conn.execute(
        f"SELECT {AXES_REPARTITION[axe]} AS libelle, COUNT(*) AS nb_documents "
        f"FROM documents d WHERE 1 = 1{filtre} GROUP BY libelle ORDER BY {ordre}",
        params,
    ).fetchall()


def _charger_restreints(conn, portee, limite=None) -> list:
    filtre, params = _filtre(portee)
    return conn.execute(
        "SELECT d.id_document, d.titre, d.auteur, d.annee, f.nom AS ufr_nom, d.discipline "
        "FROM documents d JOIN ufr f ON f.id_ufr = d.id_ufr "
        "WHERE d.niveau_acces = 'RESTREINT'" + filtre + " ORDER BY d.annee DESC, d.titre, d.id_document",
        params,
    ).fetchall()


def _charger_recherches_sans_resultat(conn, portee=None, limite=50) -> list:
    return conn.execute(
        "SELECT requete, COUNT(*) AS nb_fois, MAX(date_recherche) AS derniere_recherche "
        "FROM recherches WHERE nb_resultats = 0 GROUP BY requete "
        "ORDER BY nb_fois DESC, derniere_recherche DESC LIMIT %s",
        (limite,),
    ).fetchall()


# ---------------------------------------------------------------- routes JSON
@router.get("/globales", response_model=StatsGlobalesOut)
def globales(
    id_ufr: Optional[int] = Query(None, description="Administrateur : limiter à une UFR"),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Chiffres clés : documents, téléchargements et (administrateur) utilisateurs et recherches."""
    portee = _portee(conn, user, id_ufr)
    filtre, params = _filtre(portee)

    par_niveau = {n: 0 for n in NIVEAUX}
    for ligne in conn.execute(
        "SELECT d.niveau_acces, COUNT(*) AS n FROM documents d WHERE 1 = 1" + filtre + " GROUP BY d.niveau_acces",
        params,
    ).fetchall():
        par_niveau[ligne["niveau_acces"]] = int(ligne["n"])

    tel = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(t.date_telechargement >= NOW() - INTERVAL 30 DAY), 0) AS recents, "
        "COUNT(DISTINCT t.id_utilisateur) AS etudiants "
        "FROM telechargements t JOIN documents d ON d.id_document = t.id_document WHERE 1 = 1" + filtre,
        params,
    ).fetchone()

    ufr_nom = None
    if portee is not None:
        ufr_nom = conn.execute("SELECT nom FROM ufr WHERE id_ufr = %s", (portee,)).fetchone()["nom"]

    utilisateurs = recherches = None
    if user["role"] == "ADMIN":
        utilisateurs = {r: 0 for r in ROLES}
        for ligne in conn.execute("SELECT role, COUNT(*) AS n FROM utilisateurs GROUP BY role").fetchall():
            utilisateurs[ligne["role"]] = int(ligne["n"])
        rech = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(nb_resultats = 0), 0) AS sans FROM recherches"
        ).fetchone()
        recherches = StatsRecherchesOut(total=int(rech["total"]), sans_resultat=int(rech["sans"]))

    return StatsGlobalesOut(
        portee="UFR" if portee is not None else "GLOBALE",
        id_ufr=portee,
        ufr_nom=ufr_nom,
        documents=StatsDocumentsOut(total=sum(par_niveau.values()), par_niveau_acces=par_niveau),
        telechargements=StatsTelechargementsOut(
            total=int(tel["total"]), derniers_30_jours=int(tel["recents"]), etudiants_distincts=int(tel["etudiants"])
        ),
        utilisateurs=utilisateurs,
        recherches=recherches,
    )


@router.get("/top-documents", response_model=List[TopDocumentOut])
def top_documents(
    limite: int = Query(10, ge=1, le=100),
    id_ufr: Optional[int] = Query(None),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Documents les plus téléchargés (au moins un téléchargement)."""
    return _charger_top_documents(conn, _portee(conn, user, id_ufr), limite)


@router.get("/activite-ufr", response_model=List[ActiviteUfrOut])
def activite_ufr(
    id_ufr: Optional[int] = Query(None),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Nombre de documents et de téléchargements par UFR (le gestionnaire voit seulement la sienne)."""
    return _charger_activite_ufr(conn, _portee(conn, user, id_ufr))


@router.get("/repartition/{axe}", response_model=List[RepartitionOut])
def repartition(
    axe: str,
    id_ufr: Optional[int] = Query(None),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Répartition du fonds par `discipline`, `annee`, `type` ou `niveau_acces`."""
    return _charger_repartition(conn, _portee(conn, user, id_ufr), axe)


@router.get("/documents-restreints", response_model=List[DocumentRestreintOut])
def documents_restreints(
    id_ufr: Optional[int] = Query(None),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Liste des documents en accès restreint (embargo)."""
    return _charger_restreints(conn, _portee(conn, user, id_ufr))


@router.get("/recherches-sans-resultat", response_model=List[RechercheSansResultatOut])
def recherches_sans_resultat(
    limite: int = Query(50, ge=1, le=500),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Ce que les étudiants cherchent sans le trouver (administrateur seulement, sans identité)."""
    _admin_seulement(user)
    return _charger_recherches_sans_resultat(conn, limite=limite)


# ---------------------------------------------------------------- export CSV
# nom du jeu -> (colonnes, fonction de chargement, réservé à l'administrateur)
JEUX_EXPORT = {
    "top-documents": (("id_document", "titre", "auteur", "ufr_nom", "nb_telechargements"),
                      lambda conn, portee: _charger_top_documents(conn, portee, 1000), False),
    "activite-ufr": (("id_ufr", "nom", "nb_documents", "nb_telechargements"), _charger_activite_ufr, False),
    "repartition-discipline": (("libelle", "nb_documents"),
                               lambda conn, portee: _charger_repartition(conn, portee, "discipline"), False),
    "repartition-annee": (("libelle", "nb_documents"),
                          lambda conn, portee: _charger_repartition(conn, portee, "annee"), False),
    "documents-restreints": (("id_document", "titre", "auteur", "annee", "ufr_nom", "discipline"),
                             _charger_restreints, False),
    "recherches-sans-resultat": (("requete", "nb_fois", "derniere_recherche"),
                                 lambda conn, portee: _charger_recherches_sans_resultat(conn, limite=1000), True),
}


def _cellule(valeur) -> str:
    """Valeur CSV. Un texte qui commencerait par = + - @ serait exécuté comme formule par Excel : on le neutralise."""
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        return valeur.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valeur, str) and valeur[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valeur
    return str(valeur)


@router.get("/export/{jeu}")
def exporter_csv(
    jeu: str,
    id_ufr: Optional[int] = Query(None),
    user: dict = Depends(admin_ou_gestionnaire),
    conn=Depends(get_conn),
):
    """Export CSV (séparateur « ; », encodage UTF-8 avec BOM : s'ouvre directement dans Excel en français).

    Jeux disponibles : top-documents, activite-ufr, repartition-discipline, repartition-annee,
    documents-restreints, recherches-sans-resultat (administrateur).
    """
    if jeu not in JEUX_EXPORT:
        raise ChampInvalideError(f"Jeu inconnu. Valeurs possibles : {', '.join(JEUX_EXPORT)}.")
    colonnes, charger, admin_only = JEUX_EXPORT[jeu]
    if admin_only:
        _admin_seulement(user)
    lignes = charger(conn, _portee(conn, user, id_ufr))

    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(colonnes)
    for ligne in lignes:
        ecrivain.writerow([_cellule(ligne[c]) for c in colonnes])
    return Response(
        content=("\ufeff" + sortie.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{jeu}.csv"'},
    )
