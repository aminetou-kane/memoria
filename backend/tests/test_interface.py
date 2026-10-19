"""Étape 5 - l'interface web est servie par l'application (MySQL requis pour démarrer l'API)."""
import os
import re
from pathlib import Path

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.config import charger_env, settings
from app.database import ouvrir_connexion
from app.main import app


def _base_disponible() -> bool:
    try:
        ouvrir_connexion().close()
        return True
    except pymysql.MySQLError:
        return False


pytestmark = pytest.mark.skipif(not _base_disponible(), reason="MySQL indisponible")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_la_racine_redirige_vers_l_interface(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/app/"
    assert client.get("/sante").json()["statut"] == "ok"


def test_le_nom_de_l_application_est_configurable(client, monkeypatch):
    monkeypatch.setattr(settings, "app_nom", "Archive UGB")
    monkeypatch.setattr(settings, "app_sous_titre", "Mon sous-titre")
    donnees = client.get("/sante").json()
    assert donnees["application"] == "Archive UGB" and donnees["sous_titre"] == "Mon sous-titre"


def test_le_nom_n_est_ecrit_en_dur_que_dans_la_configuration_de_secours():
    """Pour renommer l'application, il suffit de changer APP_NOM : aucun autre fichier ne contient l'ancien nom."""
    dossier = Path(__file__).resolve().parent.parent / "app" / "static"
    for fichier in list((dossier / "js").glob("*.js")) + [dossier / "index.html", dossier / "css" / "style.css"]:
        contenu = fichier.read_text(encoding="utf-8")
        if fichier.name != "config.js":
            assert "Mémoria" not in contenu, fichier.name


@pytest.mark.parametrize("encodage", ["utf-8", "utf-8-sig", "cp1252"])
def test_le_fichier_env_est_lu_quel_que_soit_l_encodage(tmp_path, monkeypatch, encodage):
    """Le Bloc-notes de Windows peut enregistrer en ANSI : les accents ne doivent pas faire planter le démarrage."""
    monkeypatch.delenv("APP_NOM_TEST", raising=False)
    fichier = tmp_path / ".env"
    fichier.write_bytes("APP_NOM_TEST=Thèse Base é\n".encode(encodage))
    charger_env(fichier)
    assert os.environ.pop("APP_NOM_TEST") == "Thèse Base é"


def test_page_et_ressources_sont_servies(client):
    r = client.get("/app/")
    assert r.status_code == 200 and 'id="app"' in r.text
    assert r.headers["cache-control"] == "no-cache"
    # tous les fichiers référencés par la page existent vraiment
    ressources = re.findall(r'(?:src|href)="((?:js|css|vendor)/[^"]+)"', r.text)
    assert len(ressources) >= 10
    for chemin in ressources:
        reponse = client.get("/app/" + chemin)
        assert reponse.status_code == 200, chemin
        assert len(reponse.content) > 100, chemin
    assert client.get("/app/js/inexistant.js").status_code == 404


def test_l_image_de_fond_de_la_connexion_est_servie(client):
    css = client.get("/app/css/style.css").text
    images = re.findall(r'url\("\.\./(img/[^"]+)"\)', css)
    assert images == ["img/fond-connexion.jpg"]
    r = client.get("/app/" + images[0])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"


def test_aucun_affichage_dangereux_dans_le_code_de_l_interface():
    """`element.append(null)` écrit « null » à l'écran : tout passe par remplacer(), qui ignore les valeurs vides."""
    dossier = Path(__file__).resolve().parent.parent / "app" / "static" / "js"
    for fichier in dossier.glob("*.js"):
        contenu = fichier.read_text(encoding="utf-8")
        assert not re.search(r"vider\(\w+\)\.append\(", contenu), fichier.name
        assert "innerHTML" not in contenu, fichier.name


def test_le_logo_est_servi(client):
    r = client.get("/app/img/logo.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and b"<svg" in r.content


def test_aucun_script_externe():
    """L'interface fonctionne hors ligne : aucune ressource chargée depuis Internet."""
    dossier = Path(__file__).resolve().parent.parent / "app" / "static"
    page = (dossier / "index.html").read_text(encoding="utf-8")
    assert "http://" not in page and "https://" not in page
    for fichier in (dossier / "js").glob("*.js"):
        assert "innerHTML" not in fichier.read_text(encoding="utf-8"), fichier.name   # pas d'injection HTML possible


def test_l_api_reste_accessible(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/auth/me").status_code == 401
