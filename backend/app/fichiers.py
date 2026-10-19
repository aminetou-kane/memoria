"""Stockage des PDF sur disque (le nom du fichier est un identifiant aléatoire)."""
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import settings
from .exceptions import ChampInvalideError, DocumentIntrouvableError


def _dossier() -> Path:
    dossier = Path(settings.upload_dir)
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier.resolve()


def lire_pdf(fichier: UploadFile) -> bytes:
    """Lit et valide le PDF envoyé (taille maximale + signature %PDF)."""
    maximum = settings.max_upload_mb * 1024 * 1024
    contenu = fichier.file.read(maximum + 1)
    if len(contenu) > maximum:
        raise ChampInvalideError(f"Le PDF dépasse {settings.max_upload_mb} Mo.")
    if not contenu.startswith(b"%PDF-"):
        raise ChampInvalideError("Le fichier envoyé n'est pas un PDF valide.")
    return contenu


def enregistrer_pdf(contenu: bytes) -> str:
    nom = f"{uuid.uuid4().hex}.pdf"
    (_dossier() / nom).write_bytes(contenu)
    return nom


def supprimer_pdf(nom) -> None:
    if nom:
        (_dossier() / Path(nom).name).unlink(missing_ok=True)


def chemin_pdf(nom) -> Path:
    if not nom:
        raise DocumentIntrouvableError("Aucun fichier PDF n'est associé à ce document.")
    chemin = _dossier() / Path(nom).name
    if not chemin.is_file():
        raise DocumentIntrouvableError("Le fichier PDF de ce document est introuvable.")
    return chemin


def nom_de_telechargement(titre: str) -> str:
    return (re.sub(r"[^A-Za-z0-9]+", "_", titre).strip("_")[:80] or "document") + ".pdf"
