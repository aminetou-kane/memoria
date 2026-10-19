"""Étape 3 - recherche multi-critères de l'étudiant (MySQL requis)."""
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

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
RESUME_LONG = "Ce travail étudie les systèmes d'irrigation au Sénégal. " * 8


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, mdp):
    r = client.post("/auth/login", json={"email": email, "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_recherche(client):
    admin = _login(client, settings.admin_email, settings.admin_password)
    tok = "zq" + uuid.uuid4().hex[:8]          # jeton unique : isole nos documents de tout le reste
    ufrs = client.get("/ufr", headers=admin).json()
    ufr_a, ufr_b = ufrs[0]["id_ufr"], ufrs[1]["id_ufr"]

    def creer_gest(id_ufr, tag):
        email = f"{tag}.{tok}@ugb.edu.sn"
        r = client.post("/users/gestionnaires", headers=admin, json={
            "nom": "Gest", "prenom": tag, "email": email, "mot_de_passe": "Motdepasse1", "id_ufr": id_ufr})
        assert r.status_code == 201, r.text
        return r.json()["id_utilisateur"], _login(client, email, "Motdepasse1")

    id_ga, ga = creer_gest(ufr_a, "ga")
    id_gb, gb = creer_gest(ufr_b, "gb")
    e_mail, code = f"etu.{tok}@ugb.edu.sn", f"ETU{tok}"
    id_etu = client.post("/users/etudiants", headers=admin, json={
        "nom": "Fall", "prenom": "Aida", "email": e_mail, "code_etudiant": code}).json()["id_utilisateur"]
    etu = {"Authorization": "Bearer " + client.post("/auth/login-etudiant", json={
        "prenom": "Aida", "nom": "Fall", "email": e_mail, "code_etudiant": code}).json()["access_token"]}

    docs = []

    def ajouter(headers, titre, auteur, annee, type_, niveau, discipline, mots_cles, resume=None, pdf=False):
        data = {"titre": titre, "auteur": auteur, "annee": str(annee), "type": type_, "niveau_acces": niveau,
                "discipline": discipline, "mots_cles": mots_cles}
        if resume:
            data["resume"] = resume
        r = client.post("/documents", headers=headers, data=data,
                        files={"fichier": ("d.pdf", PDF, "application/pdf")} if pdf else None)
        assert r.status_code == 201, r.text
        docs.append((headers, r.json()["id_document"]))
        return r.json()["id_document"]

    def chercher(**params):
        r = client.get("/documents/recherche", headers=etu, params=params)
        assert r.status_code == 200, r.text
        return r.json()

    def ids(**params):
        return [d["id_document"] for d in chercher(**params)["resultats"]]

    try:
        d1 = ajouter(ga, f"Étude agricole {tok}", "Awa Diop", 2023, "mémoire", "TELECHARGEABLE",
                     "Agronomie", "agriculture, irrigation", RESUME_LONG, pdf=True)
        d2 = ajouter(ga, f"Finance publique {tok}", "Moussa Fall", 2022, "thèse", "CONSULTATION_SEULE",
                     "Economie", "financial, budget")
        d3 = ajouter(ga, f"Secret embargo {tok}", "Aida Sy", 2023, "mémoire", "RESTREINT",
                     "Agronomie", "agriculture")
        d4 = ajouter(gb, f"Droit foncier {tok}", "Ibou Ba", 2021, "mémoire", "CONSULTATION_SEULE",
                     "Droit", "IA, foncier")

        # --- règle 3 : l'embargo n'apparaît jamais ; tri par année décroissante
        res = chercher(q=tok)
        assert res["total"] == 3
        assert ids(q=tok) == [d1, d2, d4]
        assert d3 not in ids(q=tok, taille=50)
        assert d3 not in ids(taille=50) and ids(q=tok, titre="embargo") == []
        assert ids(annee=2023, q=tok) == [d1]                    # d3 (2023) reste caché

        # --- texte libre : mots combinés, accents et majuscules ignorés, champs multiples
        assert ids(q=f"{tok} agricole") == [d1]
        assert ids(q=f"ETUDE {tok}") == [d1]                     # « Étude » trouvé sans accent
        assert ids(q=f"{tok} irrigation") == [d1]                # trouvé via mots-clés / résumé
        assert ids(q=f"{tok} Moussa") == [d2]                    # trouvé via l'auteur
        assert ids(q=f"{tok} introuvable") == []

        # --- critères séparés
        assert ids(q=tok, titre="finance") == [d2]
        assert ids(q=tok, auteur="moussa") == [d2]
        assert ids(q=tok, discipline="agro") == [d1]             # d3 caché
        assert ids(q=tok, annee=2022) == [d2]
        assert ids(q=tok, id_ufr=ufr_b) == [d4]
        assert ids(q=tok, id_ufr=ufr_a) == [d1, d2]
        assert ids(q=tok, type="THÈSE") == [d2]                  # accent accepté
        assert ids(q=tok, type="memoire") == [d1, d4]
        assert ids(q=tok, telechargeable="true") == [d1]

        # --- mot-clé : mot entier uniquement (« ia » ne trouve pas « financial »)
        assert ids(q=tok, mot_cle="ia") == [d4]
        assert ids(q=tok, mot_cle="IA") == [d4]
        assert ids(q=tok, mot_cle="agriculture") == [d1]         # d3 caché
        assert ids(q=tok, mot_cle="agri") == []

        # --- jokers SQL saisis par l'utilisateur : traités comme du texte
        assert chercher(q=f"{tok} %")["total"] == 0
        assert chercher(q=f"{tok} _")["total"] == 0

        # --- pagination
        p1 = chercher(q=tok, taille=2)
        assert p1["total"] == 3 and len(p1["resultats"]) == 2 and p1["page"] == 1
        assert [d["id_document"] for d in chercher(q=tok, taille=2, page=2)["resultats"]] == [d4]
        assert chercher(q=tok, taille=2, page=3)["resultats"] == []

        # --- contenu d'un résultat
        fiche1 = next(d for d in chercher(q=tok)["resultats"] if d["id_document"] == d1)
        assert "chemin_pdf" not in fiche1 and "resume" not in fiche1
        assert fiche1["telechargeable"] is True and fiche1["mots_cles"] == ["agriculture", "irrigation"]
        assert len(fiche1["extrait"]) <= 201 and fiche1["extrait"].endswith("…")
        fiche2 = next(d for d in chercher(q=tok)["resultats"] if d["id_document"] == d2)
        assert fiche2["telechargeable"] is False and fiche2["extrait"] is None

        # --- erreurs et droits
        r = client.get("/documents/recherche", headers=etu, params={"type": "ROMAN"})
        assert r.status_code == 422 and r.json()["erreur"] == "ChampInvalideError"
        assert client.get("/documents/recherche", headers=etu, params={"taille": 51}).status_code == 422
        assert client.get("/documents/recherche", headers=etu, params={"page": 0}).status_code == 422
        assert client.get("/documents/recherche", headers=ga).status_code == 403
        assert client.get("/documents/recherche", headers=admin).status_code == 403
        assert client.get("/documents/recherche").status_code == 401

        # --- la fiche d'un résultat reste ouvrable ; l'embargo reste fermé
        assert client.get(f"/documents/{d2}", headers=etu).status_code == 200
        assert client.get(f"/documents/{d3}", headers=etu).status_code == 403

        # --- journal des recherches (pour les statistiques de l'étape 4)
        conn = ouvrir_connexion()
        try:
            lignes = conn.execute(
                "SELECT requete, nb_resultats FROM recherches WHERE requete = %s", (f"q={tok}",)).fetchall()
            assert lignes and all(l["nb_resultats"] == 3 for l in lignes)
            vide = conn.execute(
                "SELECT nb_resultats FROM recherches WHERE requete = %s", (f"q={tok} introuvable",)).fetchall()
            assert vide and vide[0]["nb_resultats"] == 0
        finally:
            conn.close()
    finally:
        for headers, id_doc in docs:
            client.delete(f"/documents/{id_doc}", headers=headers)
        for uid in (id_ga, id_gb, id_etu):
            client.delete(f"/users/{uid}", headers=admin)
        conn = ouvrir_connexion()
        try:
            conn.execute("DELETE FROM recherches WHERE requete LIKE %s", (f"%{tok}%",))
            conn.commit()
        finally:
            conn.close()
