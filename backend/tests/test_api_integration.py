"""Test de bout en bout : nécessite la base MySQL centre_doc initialisée (scripts db/)."""
import os
import uuid

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.config import settings
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


def _auth(client, email=None, mdp=None):
    r = client.post("/auth/login", json={
        "email": email or settings.admin_email, "mot_de_passe": mdp or settings.admin_password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parcours_admin_et_regles_metier(client):
    admin = _auth(client)
    suffixe = uuid.uuid4().hex[:6]
    ufrs = client.get("/ufr", headers=admin).json()
    assert len(ufrs) >= 7
    id_ufr = ufrs[0]["id_ufr"]

    # création d'un gestionnaire
    email = f"gest.{suffixe}@ugb.edu.sn"
    r = client.post("/users/gestionnaires", headers=admin, json={
        "nom": "Ndiaye", "prenom": "Moussa", "email": email,
        "mot_de_passe": "Motdepasse1", "id_ufr": id_ufr})
    assert r.status_code == 201, r.text
    gest = r.json()
    assert gest["role"] == "GESTIONNAIRE" and gest["ufr_nom"]

    # règle 5 : email UGB obligatoire
    r = client.post("/users/gestionnaires", headers=admin, json={
        "nom": "X", "prenom": "Y", "email": "x@gmail.com", "mot_de_passe": "Motdepasse1", "id_ufr": id_ufr})
    assert r.status_code == 422 and r.json()["erreur"] == "ChampInvalideError"

    # règle 6 : unicité de l'email
    r = client.post("/users/gestionnaires", headers=admin, json={
        "nom": "Ndiaye", "prenom": "Moussa", "email": email, "mot_de_passe": "Motdepasse1", "id_ufr": id_ufr})
    assert r.status_code == 409 and r.json()["erreur"] == "DoublonError"

    # UFR inexistante
    r = client.post("/users/gestionnaires", headers=admin, json={
        "nom": "A", "prenom": "B", "email": f"b.{suffixe}@ugb.edu.sn", "mot_de_passe": "Motdepasse1", "id_ufr": 99999})
    assert r.status_code == 404 and r.json()["erreur"] == "UfrIntrouvableError"

    # le gestionnaire se connecte mais n'a pas accès au module admin
    g = _auth(client, email, "Motdepasse1")
    r = client.get("/users", headers=g)
    assert r.status_code == 403 and r.json()["erreur"] == "AccesRefuseError"

    # mauvais mot de passe
    r = client.post("/auth/login", json={"email": email, "mot_de_passe": "faux"})
    assert r.status_code == 401 and r.json()["erreur"] == "AuthentificationError"

    # affectation à une autre UFR + recherche
    r = client.put(f"/users/{gest['id_utilisateur']}", headers=admin, json={"id_ufr": ufrs[1]["id_ufr"]})
    assert r.status_code == 200 and r.json()["id_ufr"] == ufrs[1]["id_ufr"]
    r = client.get("/users", headers=admin, params={"q": suffixe})
    assert [u["email"] for u in r.json()] == [email]

    # étudiant : création, doublon de code, connexion sans mot de passe
    code = f"ETU{suffixe}"
    e_mail = f"etu.{suffixe}@ugb.edu.sn"
    r = client.post("/users/etudiants", headers=admin, json={
        "nom": "Fall", "prenom": "Aida", "email": e_mail, "code_etudiant": code})
    assert r.status_code == 201
    r = client.post("/users/etudiants", headers=admin, json={
        "nom": "Fall", "prenom": "Aida", "email": f"autre.{suffixe}@ugb.edu.sn", "code_etudiant": code})
    assert r.status_code == 409
    r = client.post("/auth/login-etudiant", json={
        "prenom": "aida", "nom": "FALL", "email": e_mail, "code_etudiant": code})
    assert r.status_code == 200 and r.json()["role"] == "ETUDIANT"
    r = client.post("/auth/login-etudiant", json={
        "prenom": "Aida", "nom": "Autre", "email": e_mail, "code_etudiant": code})
    assert r.status_code == 401

    # UFR : doublon, suppression interdite si utilisée
    r = client.post("/ufr", headers=admin, json={"nom": ufrs[0]["nom"].upper()})
    assert r.status_code == 409
    r = client.delete(f"/ufr/{ufrs[1]['id_ufr']}", headers=admin)
    assert r.status_code == 409 and r.json()["erreur"] == "RegleMetierError"

    # suppression des comptes de test ; l'admin est protégé
    for uid in (gest["id_utilisateur"], client.get("/users", headers=admin, params={"q": e_mail}).json()[0]["id_utilisateur"]):
        assert client.delete(f"/users/{uid}", headers=admin).status_code == 204
    id_admin = client.get("/users", headers=admin, params={"role": "ADMIN"}).json()[0]["id_utilisateur"]
    assert client.delete(f"/users/{id_admin}", headers=admin).status_code == 403

    # sans jeton
    assert client.get("/users").status_code == 401
