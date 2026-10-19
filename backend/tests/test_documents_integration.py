"""Étape 2 - fonds documentaire, niveaux d'accès, téléchargements (MySQL requis)."""
import uuid
from pathlib import Path

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

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, mdp):
    r = client.post("/auth/login", json={"email": email, "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _form(titre, niveau, **extra):
    data = {"titre": titre, "auteur": "Fatou Sow", "annee": "2024", "type": "mémoire",
            "niveau_acces": niveau, "discipline": "Informatique",
            "resume": "Un résumé de test.", "mots_cles": "IA, data ; ia, BI"}
    data.update(extra)
    return data


def test_parcours_documents(client):
    admin = _login(client, settings.admin_email, settings.admin_password)
    sfx = uuid.uuid4().hex[:6]
    ufrs = client.get("/ufr", headers=admin).json()
    ufr_a, ufr_b = ufrs[0]["id_ufr"], ufrs[1]["id_ufr"]

    def creer_gest(id_ufr, tag):
        email = f"{tag}.{sfx}@ugb.edu.sn"
        r = client.post("/users/gestionnaires", headers=admin, json={
            "nom": "Gest", "prenom": tag, "email": email, "mot_de_passe": "Motdepasse1", "id_ufr": id_ufr})
        assert r.status_code == 201, r.text
        return r.json()["id_utilisateur"], _login(client, email, "Motdepasse1")

    id_ga, ga = creer_gest(ufr_a, "ga")
    id_gb, gb = creer_gest(ufr_b, "gb")
    e_mail, code = f"etu.{sfx}@ugb.edu.sn", f"ETU{sfx}"
    r = client.post("/users/etudiants", headers=admin, json={
        "nom": "Fall", "prenom": "Aida", "email": e_mail, "code_etudiant": code})
    id_etu = r.json()["id_utilisateur"]
    etu = {"Authorization": "Bearer " + client.post("/auth/login-etudiant", json={
        "prenom": "Aida", "nom": "Fall", "email": e_mail, "code_etudiant": code}).json()["access_token"]}

    ids = []
    try:
        # --- création (le document est forcément rattaché à l'UFR du gestionnaire)
        r = client.post("/documents", headers=ga, data=_form(f"Doc libre {sfx}", "TELECHARGEABLE"),
                        files={"fichier": ("m.pdf", PDF, "application/pdf")})
        assert r.status_code == 201, r.text
        libre = r.json(); ids.append(libre["id_document"])
        assert libre["id_ufr"] == ufr_a and libre["type"] == "MEMOIRE"
        assert libre["mots_cles"] == ["IA", "data", "BI"]          # doublon 'ia' supprimé
        assert libre["telechargeable"] and "chemin_pdf" not in libre

        r = client.post("/documents", headers=ga, data=_form(f"Doc consult {sfx}", "CONSULTATION_SEULE"))
        consult = r.json(); ids.append(consult["id_document"])
        assert r.status_code == 201 and not consult["telechargeable"]

        r = client.post("/documents", headers=ga, data=_form(f"Doc embargo {sfx}", "RESTREINT"))
        embargo = r.json(); ids.append(embargo["id_document"])

        # --- règles de validation
        r = client.post("/documents", headers=ga, data=_form(f"Sans pdf {sfx}", "TELECHARGEABLE"))
        assert r.status_code == 422 and r.json()["erreur"] == "ChampInvalideError"
        r = client.post("/documents", headers=ga, data=_form(f"Faux pdf {sfx}", "TELECHARGEABLE"),
                        files={"fichier": ("x.pdf", b"pas un pdf", "application/pdf")})
        assert r.status_code == 422
        r = client.post("/documents", headers=ga, data=_form(f"Doc libre {sfx}", "RESTREINT"))
        assert r.status_code == 409 and r.json()["erreur"] == "DoublonError"
        r = client.post("/documents", headers=ga, data=_form(f"Annee {sfx}", "RESTREINT", annee="1800"))
        assert r.status_code == 422
        r = client.post("/documents", headers=ga, data=_form(f"Type {sfx}", "RESTREINT", type="ROMAN"))
        assert r.status_code == 422

        # --- droits : étudiant et autre UFR ne peuvent pas gérer
        r = client.post("/documents", headers=etu, data=_form(f"Etu {sfx}", "RESTREINT"))
        assert r.status_code == 403
        r = client.put(f"/documents/{libre['id_document']}", headers=gb, data={"titre": "Piraté"})
        assert r.status_code == 403 and r.json()["erreur"] == "AccesRefuseError"
        assert client.delete(f"/documents/{libre['id_document']}", headers=gb).status_code == 403
        assert client.get(f"/documents/{libre['id_document']}", headers=gb).status_code == 403
        assert client.get("/documents/gestion", headers=gb).json() == [] or all(
            d["id_ufr"] == ufr_b for d in client.get("/documents/gestion", headers=gb).json())

        # --- fiche étudiant selon le niveau d'accès (règles 2 et 3)
        assert client.get(f"/documents/{libre['id_document']}", headers=etu).status_code == 200
        r = client.get(f"/documents/{consult['id_document']}", headers=etu)
        assert r.status_code == 200 and r.json()["resume"] == "Un résumé de test."
        r = client.get(f"/documents/{embargo['id_document']}", headers=etu)
        assert r.status_code == 403
        assert client.get(f"/documents/{embargo['id_document']}", headers=ga).status_code == 200
        assert client.get("/documents/999999", headers=etu).status_code == 404

        # --- téléchargement (règle 1)
        r = client.get(f"/documents/{libre['id_document']}/download", headers=etu)
        assert r.status_code == 200 and r.content == PDF
        assert r.headers["content-type"] == "application/pdf"
        for doc in (consult, embargo):
            r = client.get(f"/documents/{doc['id_document']}/download", headers=etu)
            assert r.status_code == 403 and r.json()["erreur"] == "AccesRefuseError"
        assert client.get(f"/documents/{libre['id_document']}/download", headers=ga).status_code == 403
        assert client.get(f"/documents/{libre['id_document']}/download").status_code == 401

        # --- historiques
        client.get(f"/documents/{libre['id_document']}/download", headers=etu)   # 2e téléchargement
        mes = client.get("/telechargements/moi", headers=etu).json()
        assert len(mes) == 2 and mes[0]["titre"] == libre["titre"]
        hist = client.get(f"/telechargements/document/{libre['id_document']}", headers=ga).json()
        assert len(hist) == 2 and hist[0]["code_etudiant"] == code
        assert client.get(f"/telechargements/document/{libre['id_document']}", headers=gb).status_code == 403
        assert len(client.get("/telechargements/gestion", headers=ga).json()) == 2
        assert client.get("/telechargements/gestion", headers=gb).json() == []
        dispo = client.get(f"/documents/{libre['id_document']}/disponibilite", headers=ga).json()
        assert dispo["nb_telechargements"] == 2 and dispo["telechargeable"]

        # --- modification : passage en consultation seule, puis remplacement du PDF
        r = client.put(f"/documents/{libre['id_document']}", headers=ga,
                       data={"niveau_acces": "CONSULTATION_SEULE", "encadrant": "Pr. Ba"})
        assert r.status_code == 200 and r.json()["encadrant"] == "Pr. Ba" and not r.json()["telechargeable"]
        assert client.get(f"/documents/{libre['id_document']}/download", headers=etu).status_code == 403
        r = client.put(f"/documents/{consult['id_document']}", headers=ga,
                       data={"niveau_acces": "TELECHARGEABLE"})
        assert r.status_code == 422                                 # pas de PDF
        r = client.put(f"/documents/{consult['id_document']}", headers=ga,
                       data={"niveau_acces": "TELECHARGEABLE"},
                       files={"fichier": ("n.pdf", PDF + b"v2", "application/pdf")})
        assert r.status_code == 200 and r.json()["telechargeable"]
        assert client.get(f"/documents/{consult['id_document']}/download", headers=etu).content == PDF + b"v2"
        assert client.put(f"/documents/{consult['id_document']}", headers=ga).status_code == 422

        # --- suppression : la ligne et le fichier disparaissent
        fichiers_avant = len(list(Path(settings.upload_dir).glob("*.pdf")))
        assert client.delete(f"/documents/{consult['id_document']}", headers=ga).status_code == 204
        assert len(list(Path(settings.upload_dir).glob("*.pdf"))) == fichiers_avant - 1
        ids.remove(consult["id_document"])
        assert client.get(f"/documents/{consult['id_document']}", headers=ga).status_code == 404
    finally:
        for i in ids:
            client.delete(f"/documents/{i}", headers=ga)
        for uid in (id_ga, id_gb, id_etu):
            client.delete(f"/users/{uid}", headers=admin)
