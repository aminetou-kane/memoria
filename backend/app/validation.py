import re
import unicodedata
from datetime import date

from .exceptions import ChampInvalideError

EMAIL_UGB = re.compile(r"[a-z0-9._%+\-]+@ugb\.edu\.sn")


def exiger_texte(valeur, champ: str, max_len: int = 150) -> str:
    if valeur is None or not str(valeur).strip():
        raise ChampInvalideError(f"Le champ '{champ}' est obligatoire.")
    valeur = str(valeur).strip()
    if len(valeur) > max_len:
        raise ChampInvalideError(f"Le champ '{champ}' dépasse {max_len} caractères.")
    return valeur


def valider_email_ugb(email) -> str:
    email = exiger_texte(email, "email").lower()
    if not EMAIL_UGB.fullmatch(email):
        raise ChampInvalideError("L'email doit être un email UGB (format ...@ugb.edu.sn).")
    return email


def valider_mot_de_passe(mot_de_passe) -> str:
    if mot_de_passe is None or len(mot_de_passe) < 8:
        raise ChampInvalideError("Le mot de passe doit contenir au moins 8 caractères.")
    if len(mot_de_passe.encode()) > 72:
        raise ChampInvalideError("Le mot de passe est trop long (72 octets maximum).")
    return mot_de_passe


# ---------------------------------------------------------------- documents
TYPES_DOCUMENT = ("THESE", "MEMOIRE")
NIVEAUX_ACCES = ("TELECHARGEABLE", "CONSULTATION_SEULE", "RESTREINT")


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def valider_type_document(valeur) -> str:
    v = _sans_accents(exiger_texte(valeur, "type")).upper()
    if v not in TYPES_DOCUMENT:
        raise ChampInvalideError("Le type doit être THESE ou MEMOIRE.")
    return v


def valider_niveau_acces(valeur) -> str:
    v = exiger_texte(valeur, "niveau_acces").upper()
    if v not in NIVEAUX_ACCES:
        raise ChampInvalideError("Le niveau d'accès doit être TELECHARGEABLE, CONSULTATION_SEULE ou RESTREINT.")
    return v


def valider_annee(valeur) -> int:
    if valeur is None or not (1950 <= valeur <= date.today().year + 1):
        raise ChampInvalideError(f"L'année doit être comprise entre 1950 et {date.today().year + 1}.")
    return valeur


def normaliser_mots_cles(texte):
    """'IA, data ; ia' -> 'IA, data' (sans doublons, ordre conservé). Renvoie None si vide."""
    if not texte:
        return None
    vus = set()
    mots = []
    for mot in re.split(r"[,;]", texte):
        mot = mot.strip()
        if mot and mot.lower() not in vus:
            vus.add(mot.lower())
            mots.append(mot)
    return ", ".join(mots) or None


def mots_cles_en_liste(texte) -> list:
    return [m.strip() for m in texte.split(",") if m.strip()] if texte else []
