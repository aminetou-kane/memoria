"""Mode démonstration : prépare une instance publique que les recruteurs peuvent tester sans créer de compte.

Activé par DEMO_MODE=true. Au démarrage, l'application :
  1. crée les tables si la base est vide (db/01_schema.sql) et les UFR (db/02_seed.sql) ;
  2. charge les données fictives (scripts/donnees_demo.py) si elles n'existent pas encore ;
  3. régénère les PDF manquants (les hébergeurs gratuits effacent le disque à chaque redémarrage).
"""
import re
import sys
from pathlib import Path

from .config import settings
from .database import ouvrir_connexion
from .fichiers import _dossier

DOSSIER_BACKEND = Path(__file__).resolve().parent.parent
DOSSIER_SQL = DOSSIER_BACKEND.parent / "db"

# Comptes affichés sur la page de connexion (créés par scripts/donnees_demo.py)
MOT_DE_PASSE_DEMO = "Demo2026!"


def comptes_demo() -> list[dict]:
    """Comptes de test proposés sur la page de connexion. Vide si le mode démo est désactivé."""
    if not settings.demo_mode:
        return []
    return [
        {
            "role": "ETUDIANT", "libelle": "Étudiant",
            "description": "Rechercher, consulter et télécharger des mémoires",
            "prenom": "Mariama", "nom": "Fall",
            "email": "demo.mariama.fall@ugb.edu.sn", "code_etudiant": "DMO2026001",
        },
        {
            "role": "GESTIONNAIRE", "libelle": "Gestionnaire",
            "description": "Gérer les documents d'une UFR (ajout, niveaux d'accès)",
            "email": "demo.gestionnaire.sat@ugb.edu.sn", "mot_de_passe": MOT_DE_PASSE_DEMO,
        },
        {
            "role": "ADMIN", "libelle": "Administrateur",
            "description": "Comptes, UFR et tableau de bord statistique",
            "email": settings.admin_email, "mot_de_passe": settings.admin_password,
        },
    ]


def _instructions_sql(fichier: Path) -> list[str]:
    """Découpe un script SQL en instructions, sans CREATE DATABASE / USE (la base est déjà choisie par l'hébergeur)."""
    texte = fichier.read_text(encoding="utf-8")
    texte = "\n".join(re.sub(r"\s--.*$", "", ligne) if not ligne.lstrip().startswith("--") else "" for ligne in texte.splitlines())
    instructions = [i.strip() for i in texte.split(";") if i.strip()]
    return [i for i in instructions if not re.match(r"(CREATE DATABASE|USE)\b", i, re.IGNORECASE)]


def _creer_base_si_absente() -> None:
    """Sur un MySQL local, crée la base si besoin. Sur un hébergeur, la base existe déjà : on ignore l'erreur."""
    try:
        conn = ouvrir_connexion(avec_base=False)
    except Exception:
        return
    try:
        conn.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def initialiser_schema() -> bool:
    """Importe le schéma et les UFR si la table « utilisateurs » n'existe pas. Renvoie True si la base a été créée."""
    _creer_base_si_absente()
    conn = ouvrir_connexion()
    try:
        existe = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'utilisateurs'"
        ).fetchone()
        if existe:
            return False
        for fichier in ("01_schema.sql", "02_seed.sql"):
            for instruction in _instructions_sql(DOSSIER_SQL / fichier):
                conn.execute(instruction)
        conn.commit()
        return True
    finally:
        conn.close()


def charger_donnees_si_absentes() -> None:
    """Charge les données fictives une seule fois (reconnaissables à leur email « demo.* »)."""
    sys.path.insert(0, str(DOSSIER_BACKEND))
    from scripts import donnees_demo

    conn = ouvrir_connexion()
    try:
        if donnees_demo.etat(conn)["gestionnaires"] == 0:
            donnees_demo.charger(conn)
    finally:
        conn.close()


def regenerer_pdf_manquants() -> int:
    """Recrée les PDF de démonstration absents du disque (même nom de fichier, contenu fictif)."""
    sys.path.insert(0, str(DOSSIER_BACKEND))
    from scripts.donnees_demo import pdf_minimal

    dossier = _dossier()
    conn = ouvrir_connexion()
    try:
        lignes = conn.execute(
            "SELECT d.titre, d.auteur, d.annee, d.discipline, d.chemin_pdf, u.nom AS ufr "
            "FROM documents d JOIN ufr u ON u.id_ufr = d.id_ufr WHERE d.chemin_pdf IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    recrees = 0
    for ligne in lignes:
        chemin = dossier / Path(ligne["chemin_pdf"]).name
        if not chemin.is_file():
            chemin.write_bytes(pdf_minimal(ligne["titre"], ligne["auteur"], ligne["annee"], ligne["discipline"] or "", ligne["ufr"]))
            recrees += 1
    return recrees


def preparer_demo() -> None:
    """Appelé au démarrage quand DEMO_MODE=true. Ne doit jamais empêcher l'application de démarrer."""
    try:
        initialiser_schema()
    except Exception as erreur:  # noqa: BLE001
        print(f"[demo] Impossible d'initialiser le schéma : {erreur}")



def completer_demo() -> None:
    """Deuxième étape (après la création du compte administrateur) : données fictives et PDF."""
    try:
        charger_donnees_si_absentes()
        recrees = regenerer_pdf_manquants()
        if recrees:
            print(f"[demo] {recrees} PDF de démonstration régénérés.")
    except Exception as erreur:  # noqa: BLE001
        print(f"[demo] Données de démonstration non chargées : {erreur}")
