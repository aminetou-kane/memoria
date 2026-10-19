from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from ..database import get_conn
from ..deps import require_roles
from ..exceptions import (
    AccesRefuseError,
    ChampInvalideError,
    DocumentIntrouvableError,
    DoublonError,
)
from ..fichiers import chemin_pdf, enregistrer_pdf, lire_pdf, nom_de_telechargement, supprimer_pdf
from ..schemas import DisponibiliteOut, DocumentOut
from ..validation import (
    exiger_texte,
    mots_cles_en_liste,
    normaliser_mots_cles,
    valider_annee,
    valider_niveau_acces,
    valider_type_document,
)

router = APIRouter(prefix="/documents", tags=["Fonds documentaire"])

gestionnaire_only = require_roles("GESTIONNAIRE")
etudiant_ou_gestionnaire = require_roles("ETUDIANT", "GESTIONNAIRE")
etudiant_only = require_roles("ETUDIANT")

SELECT_DOCUMENT = """
    SELECT d.id_document, d.titre, d.auteur, d.encadrant, d.annee, d.type, d.id_ufr,
           f.nom AS ufr_nom, d.discipline, d.resume, d.mots_cles, d.chemin_pdf,
           d.niveau_acces, d.cree_le
    FROM documents d
    JOIN ufr f ON f.id_ufr = d.id_ufr
"""


# ---------------------------------------------------------------- utilitaires
def _charger(conn, id_document: int) -> dict:
    doc = conn.execute(SELECT_DOCUMENT + " WHERE d.id_document = %s", (id_document,)).fetchone()
    if doc is None:
        raise DocumentIntrouvableError(f"Document {id_document} introuvable.")
    return doc


def _sortie(doc: dict) -> DocumentOut:
    """Convertit une ligne SQL en réponse API (le chemin du PDF n'est jamais exposé)."""
    return DocumentOut(
        id_document=doc["id_document"],
        titre=doc["titre"],
        auteur=doc["auteur"],
        encadrant=doc["encadrant"],
        annee=doc["annee"],
        type=doc["type"],
        id_ufr=doc["id_ufr"],
        ufr_nom=doc["ufr_nom"],
        discipline=doc["discipline"],
        resume=doc["resume"],
        mots_cles=mots_cles_en_liste(doc["mots_cles"]),
        niveau_acces=doc["niveau_acces"],
        pdf_disponible=bool(doc["chemin_pdf"]),
        telechargeable=doc["niveau_acces"] == "TELECHARGEABLE" and bool(doc["chemin_pdf"]),
        cree_le=doc["cree_le"],
    )


def _verifier_ufr_du_gestionnaire(user: dict, doc: dict) -> None:
    """Règle 4 : un gestionnaire ne gère que les documents de son UFR."""
    if doc["id_ufr"] != user["id_ufr"]:
        raise AccesRefuseError("Ce document appartient à une autre UFR.")


def _verifier_doublon(conn, titre, auteur, annee, exclude_id=None) -> None:
    existe = conn.execute(
        "SELECT 1 FROM documents WHERE lower(titre) = lower(%s) AND lower(auteur) = lower(%s) "
        "AND annee = %s AND NOT (id_document <=> %s)",
        (titre, auteur, annee, exclude_id),
    ).fetchone()
    if existe:
        raise DoublonError("Un document avec le même titre, le même auteur et la même année existe déjà.")


def _fichier_present(fichier: Optional[UploadFile]) -> bool:
    return fichier is not None and bool(fichier.filename)


# ---------------------------------------------------------------- gestionnaire
@router.get("/gestion", response_model=List[DocumentOut])
def lister_mes_documents(
    q: Optional[str] = Query(None, description="Filtre sur le titre ou l'auteur"),
    user: dict = Depends(gestionnaire_only),
    conn=Depends(get_conn),
):
    """Documents de l'UFR du gestionnaire connecté (tous niveaux d'accès)."""
    sql = SELECT_DOCUMENT + " WHERE d.id_ufr = %s"
    params = [user["id_ufr"]]
    if q and q.strip():
        sql += " AND (d.titre LIKE %s OR d.auteur LIKE %s)"
        params += [f"%{q.strip()}%"] * 2
    sql += " ORDER BY d.annee DESC, d.titre"
    return [_sortie(d) for d in conn.execute(sql, params).fetchall()]


@router.post("", response_model=DocumentOut, status_code=201)
def ajouter(
    titre: str = Form(...),
    auteur: str = Form(...),
    annee: int = Form(...),
    type_document: str = Form(..., alias="type"),
    niveau_acces: str = Form(...),
    encadrant: Optional[str] = Form(None),
    discipline: Optional[str] = Form(None),
    resume: Optional[str] = Form(None),
    mots_cles: Optional[str] = Form(None),
    fichier: Optional[UploadFile] = File(None, description="PDF du document"),
    user: dict = Depends(gestionnaire_only),
    conn=Depends(get_conn),
):
    titre = exiger_texte(titre, "titre", 255)
    auteur = exiger_texte(auteur, "auteur", 150)
    annee = valider_annee(annee)
    type_document = valider_type_document(type_document)
    niveau_acces = valider_niveau_acces(niveau_acces)
    encadrant = encadrant.strip() or None if encadrant else None
    discipline = discipline.strip() or None if discipline else None
    resume = resume.strip() or None if resume else None

    avec_pdf = _fichier_present(fichier)
    if niveau_acces == "TELECHARGEABLE" and not avec_pdf:
        raise ChampInvalideError("Un document TELECHARGEABLE doit avoir un fichier PDF.")
    _verifier_doublon(conn, titre, auteur, annee)
    contenu = lire_pdf(fichier) if avec_pdf else None

    nom_fichier = enregistrer_pdf(contenu) if contenu else None
    try:
        curseur = conn.execute(
            "INSERT INTO documents (titre, auteur, encadrant, annee, type, id_ufr, discipline, resume, "
            "mots_cles, chemin_pdf, niveau_acces, cree_par) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (titre, auteur, encadrant, annee, type_document, user["id_ufr"], discipline, resume,
             normaliser_mots_cles(mots_cles), nom_fichier, niveau_acces, user["id_utilisateur"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        supprimer_pdf(nom_fichier)
        raise
    return _sortie(_charger(conn, curseur.lastrowid))


@router.put("/{id_document}", response_model=DocumentOut)
def modifier(
    id_document: int,
    titre: Optional[str] = Form(None),
    auteur: Optional[str] = Form(None),
    annee: Optional[int] = Form(None),
    type_document: Optional[str] = Form(None, alias="type"),
    niveau_acces: Optional[str] = Form(None),
    encadrant: Optional[str] = Form(None),
    discipline: Optional[str] = Form(None),
    resume: Optional[str] = Form(None),
    mots_cles: Optional[str] = Form(None),
    fichier: Optional[UploadFile] = File(None, description="Nouveau PDF (remplace l'ancien)"),
    user: dict = Depends(gestionnaire_only),
    conn=Depends(get_conn),
):
    """Modification partielle : seuls les champs fournis sont changés."""
    doc = _charger(conn, id_document)
    _verifier_ufr_du_gestionnaire(user, doc)

    champs = {}
    if titre is not None:
        champs["titre"] = exiger_texte(titre, "titre", 255)
    if auteur is not None:
        champs["auteur"] = exiger_texte(auteur, "auteur", 150)
    if annee is not None:
        champs["annee"] = valider_annee(annee)
    if type_document is not None:
        champs["type"] = valider_type_document(type_document)
    if niveau_acces is not None:
        champs["niveau_acces"] = valider_niveau_acces(niveau_acces)
    for nom, valeur in (("encadrant", encadrant), ("discipline", discipline), ("resume", resume)):
        if valeur is not None:
            champs[nom] = valeur.strip() or None
    if mots_cles is not None:
        champs["mots_cles"] = normaliser_mots_cles(mots_cles)

    nouveau_pdf = _fichier_present(fichier)
    niveau_final = champs.get("niveau_acces", doc["niveau_acces"])
    if niveau_final == "TELECHARGEABLE" and not (nouveau_pdf or doc["chemin_pdf"]):
        raise ChampInvalideError("Un document TELECHARGEABLE doit avoir un fichier PDF.")
    if not champs and not nouveau_pdf:
        raise ChampInvalideError("Aucune modification fournie.")

    _verifier_doublon(
        conn,
        champs.get("titre", doc["titre"]),
        champs.get("auteur", doc["auteur"]),
        champs.get("annee", doc["annee"]),
        exclude_id=id_document,
    )

    ancien_fichier = doc["chemin_pdf"]
    nom_fichier = None
    if nouveau_pdf:
        nom_fichier = enregistrer_pdf(lire_pdf(fichier))
        champs["chemin_pdf"] = nom_fichier
    try:
        # Les noms de colonnes viennent du dictionnaire ci-dessus (jamais de l'utilisateur).
        assignations = ", ".join(f"{col} = %s" for col in champs)
        conn.execute(
            f"UPDATE documents SET {assignations} WHERE id_document = %s",
            [*champs.values(), id_document],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        supprimer_pdf(nom_fichier)
        raise
    if nouveau_pdf:
        supprimer_pdf(ancien_fichier)
    return _sortie(_charger(conn, id_document))


@router.delete("/{id_document}", status_code=204)
def supprimer(id_document: int, user: dict = Depends(gestionnaire_only), conn=Depends(get_conn)):
    doc = _charger(conn, id_document)
    _verifier_ufr_du_gestionnaire(user, doc)
    conn.execute("DELETE FROM documents WHERE id_document = %s", (id_document,))
    conn.commit()
    supprimer_pdf(doc["chemin_pdf"])


@router.get("/{id_document}/disponibilite", response_model=DisponibiliteOut)
def disponibilite(id_document: int, user: dict = Depends(gestionnaire_only), conn=Depends(get_conn)):
    """Disponibilité du document et résumé de son historique de téléchargements."""
    doc = _charger(conn, id_document)
    _verifier_ufr_du_gestionnaire(user, doc)
    stats = conn.execute(
        "SELECT count(*) AS n, max(date_telechargement) AS dernier "
        "FROM telechargements WHERE id_document = %s",
        (id_document,),
    ).fetchone()
    return DisponibiliteOut(
        id_document=id_document,
        niveau_acces=doc["niveau_acces"],
        pdf_disponible=bool(doc["chemin_pdf"]),
        telechargeable=doc["niveau_acces"] == "TELECHARGEABLE" and bool(doc["chemin_pdf"]),
        nb_telechargements=stats["n"],
        dernier_telechargement=stats["dernier"],
    )


# ---------------------------------------------------------------- étudiant (et gestionnaire en lecture)
@router.get("/{id_document}", response_model=DocumentOut)
def fiche(id_document: int, user: dict = Depends(etudiant_ou_gestionnaire), conn=Depends(get_conn)):
    """Fiche détaillée.
    - RESTREINT (embargo) : ni consultable ni téléchargeable par l'étudiant (règle 3).
    - CONSULTATION_SEULE / TELECHARGEABLE : métadonnées et résumé.
    Un gestionnaire voit toutes les fiches de son UFR."""
    doc = _charger(conn, id_document)
    if user["role"] == "GESTIONNAIRE":
        _verifier_ufr_du_gestionnaire(user, doc)
    elif doc["niveau_acces"] == "RESTREINT":
        raise AccesRefuseError("Ce document est sous embargo : il n'est ni consultable ni téléchargeable.")
    return _sortie(doc)


@router.get("/{id_document}/download")
def telecharger(id_document: int, user: dict = Depends(etudiant_only), conn=Depends(get_conn)):
    """Télécharge le PDF si et seulement si le niveau d'accès l'autorise (règles 1 à 3)."""
    doc = _charger(conn, id_document)
    if doc["niveau_acces"] == "RESTREINT":
        raise AccesRefuseError("Ce document est sous embargo : il n'est ni consultable ni téléchargeable.")
    if doc["niveau_acces"] != "TELECHARGEABLE":
        raise AccesRefuseError("Ce document est en consultation seule : le PDF n'est pas téléchargeable.")
    chemin = chemin_pdf(doc["chemin_pdf"])  # lève DocumentIntrouvableError si absent

    conn.execute(
        "INSERT INTO telechargements (id_utilisateur, id_document) VALUES (%s, %s)",
        (user["id_utilisateur"], id_document),
    )
    conn.commit()
    return FileResponse(chemin, media_type="application/pdf", filename=nom_de_telechargement(doc["titre"]))
