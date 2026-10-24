import os
from pathlib import Path

from dotenv import load_dotenv

def charger_env(chemin: Path) -> None:
    """Charge le fichier .env. Accepte l'UTF-8 (avec ou sans BOM) et l'ANSI du vieux Bloc-notes de Windows."""
    if not chemin.is_file():
        return
    try:
        load_dotenv(chemin, encoding="utf-8-sig")
    except UnicodeDecodeError:
        load_dotenv(chemin, encoding="cp1252")


# Charge backend/.env s'il existe (voir .env.example)
charger_env(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    # Connexion MySQL (valeurs par défaut de WAMP : root sans mot de passe)
    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_user: str = os.getenv("DB_USER", "root")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_name: str = os.getenv("DB_NAME", "centre_doc")
    # Bases MySQL hébergées (TiDB Cloud, Aiven, PlanetScale...) : connexion chiffrée obligatoire
    db_ssl: bool = os.getenv("DB_SSL", "false").strip().lower() in ("1", "true", "oui", "yes")

    # Mode démonstration (déploiement pour recruteurs) : affiche des comptes de test sur la page de connexion,
    # crée la base et les données fictives au démarrage. À laisser à "false" hors démonstration.
    demo_mode: bool = os.getenv("DEMO_MODE", "false").strip().lower() in ("1", "true", "oui", "yes")

    # Nom affiché dans l'interface (page de connexion, en-tête, onglet du navigateur)
    app_nom: str = os.getenv("APP_NOM", "Mémoria")
    app_sous_titre: str = os.getenv("APP_SOUS_TITRE", "Gestion et recherche des thèses et mémoires")

    cors_origins: list = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-en-production-secret-de-32-caracteres-minimum")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@ugb.edu.sn")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "Admin123!")


settings = Settings()
