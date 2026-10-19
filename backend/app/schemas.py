from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    mot_de_passe: str


class LoginEtudiantIn(BaseModel):
    prenom: str
    nom: str
    email: str
    code_etudiant: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    nom: str
    prenom: str


class UfrIn(BaseModel):
    nom: str


class UfrOut(BaseModel):
    id_ufr: int
    nom: str


class GestionnaireIn(BaseModel):
    nom: str
    prenom: str
    email: str
    mot_de_passe: str
    id_ufr: int


class EtudiantIn(BaseModel):
    nom: str
    prenom: str
    email: str
    code_etudiant: str


class UtilisateurUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    id_ufr: Optional[int] = None
    code_etudiant: Optional[str] = None
    mot_de_passe: Optional[str] = None


class UtilisateurOut(BaseModel):
    id_utilisateur: int
    nom: str
    prenom: str
    email: str
    role: str
    id_ufr: Optional[int] = None
    ufr_nom: Optional[str] = None
    code_etudiant: Optional[str] = None


class DocumentOut(BaseModel):
    id_document: int
    titre: str
    auteur: str
    encadrant: Optional[str] = None
    annee: int
    type: str
    id_ufr: int
    ufr_nom: str
    discipline: Optional[str] = None
    resume: Optional[str] = None
    mots_cles: list[str] = []
    niveau_acces: str
    pdf_disponible: bool
    telechargeable: bool
    cree_le: datetime


class TelechargementGestionOut(BaseModel):
    id_telechargement: int
    id_document: int
    titre: str
    id_utilisateur: int
    nom: str
    prenom: str
    email: str
    code_etudiant: Optional[str] = None
    date_telechargement: datetime


class MonTelechargementOut(BaseModel):
    id_telechargement: int
    id_document: int
    titre: str
    auteur: str
    date_telechargement: datetime


class DisponibiliteOut(BaseModel):
    id_document: int
    niveau_acces: str
    pdf_disponible: bool
    telechargeable: bool
    nb_telechargements: int
    dernier_telechargement: Optional[datetime] = None


class DocumentListeOut(BaseModel):
    """Résultat de recherche : version allégée d'un document (résumé raccourci en extrait)."""
    id_document: int
    titre: str
    auteur: str
    encadrant: Optional[str] = None
    annee: int
    type: str
    id_ufr: int
    ufr_nom: str
    discipline: Optional[str] = None
    mots_cles: list[str] = []
    niveau_acces: str
    telechargeable: bool
    extrait: Optional[str] = None


class RechercheOut(BaseModel):
    total: int
    page: int
    taille: int
    resultats: list[DocumentListeOut]


# ---------------------------------------------------------------- statistiques (étape 4)
class StatsDocumentsOut(BaseModel):
    total: int
    par_niveau_acces: dict[str, int]


class StatsTelechargementsOut(BaseModel):
    total: int
    derniers_30_jours: int
    etudiants_distincts: int


class StatsRecherchesOut(BaseModel):
    total: int
    sans_resultat: int


class StatsGlobalesOut(BaseModel):
    portee: str                              # « GLOBALE » ou « UFR »
    id_ufr: Optional[int] = None
    ufr_nom: Optional[str] = None
    documents: StatsDocumentsOut
    telechargements: StatsTelechargementsOut
    utilisateurs: Optional[dict[str, int]] = None   # administrateur seulement
    recherches: Optional[StatsRecherchesOut] = None  # administrateur seulement


class TopDocumentOut(BaseModel):
    id_document: int
    titre: str
    auteur: str
    ufr_nom: str
    nb_telechargements: int


class ActiviteUfrOut(BaseModel):
    id_ufr: int
    nom: str
    nb_documents: int
    nb_telechargements: int


class RepartitionOut(BaseModel):
    libelle: str
    nb_documents: int


class DocumentRestreintOut(BaseModel):
    id_document: int
    titre: str
    auteur: str
    annee: int
    ufr_nom: str
    discipline: Optional[str] = None


class RechercheSansResultatOut(BaseModel):
    requete: str
    nb_fois: int
    derniere_recherche: datetime
