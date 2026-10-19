"""Étape 4 - statistiques et export CSV (MySQL requis).

Les chiffres sont comparés à un état « avant » : le test reste valable même si la base contient déjà des données.
"""
import csv
import io
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


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, mdp):
    r = client.post("/auth/login", json={"email": email, "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _nb(liste, cle, valeur, champ="nb_documents"):
    """Valeur de `champ` pour l'entrée dont `cle` == `valeur` (0 si absente)."""
    return next((x[champ] for x in liste if x[cle] == valeur), 0)


def test_statistiques(client):
    admin = _login(client, settings.admin_email, settings.admin_password)
    tok = "zq" + uuid.uuid4().hex[:8]
    ufrs = client.get("/ufr", headers=admin).json()
    ufr_a, ufr_b = ufrs[0]["id_ufr"], ufrs[1]["id_ufr"]

    def creer_gest(id_ufr, tag):
        email = f"{tag}.{tok}@ugb.edu.sn"
        r = client.post("/users/gestionnaires", headers=admin, json={
            "nom": "Gest", "prenom": tag, "email": email, "mot_de_passe": "Motdepasse1", "id_ufr": id_ufr})
        assert r.status_code == 201, r.text
        return r.json()["id_utilisateur"], _login(client, email, "Motdepasse1")

    def creer_etu(tag):
        email, code = f"{tag}.{tok}@ugb.edu.sn", f"{tag.upper()}{tok}"
        uid = client.post("/users/etudiants", headers=admin, json={
            "nom": "Etu", "prenom": tag, "email": email, "code_etudiant": code}).json()["id_utilisateur"]
        jeton = client.post("/auth/login-etudiant", json={
            "prenom": tag, "nom": "Etu", "email": email, "code_etudiant": code}).json()["access_token"]
        return uid, {"Authorization": f"Bearer {jeton}"}

    utilisateurs0 = client.get("/statistiques/globales", headers=admin).json()["utilisateurs"]   # avant les comptes de test
    id_ga, ga = creer_gest(ufr_a, "ga")
    id_gb, gb = creer_gest(ufr_b, "gb")
    id_s1, s1 = creer_etu("s1")
    id_s2, s2 = creer_etu("s2")

    # --- état « avant »
    glob_a0 = client.get("/statistiques/globales", headers=admin, params={"id_ufr": ufr_a}).json()
    glob_b0 = client.get("/statistiques/globales", headers=admin, params={"id_ufr": ufr_b}).json()
    glob0 = client.get("/statistiques/globales", headers=admin).json()
    act0 = client.get("/statistiques/activite-ufr", headers=admin).json()
    ann0 = client.get("/statistiques/repartition/annee", headers=admin).json()
    nonrens0 = _nb(client.get("/statistiques/repartition/discipline", headers=admin).json(),
                   "libelle", "Non renseignée")

    docs = []

    def ajouter(headers, titre, niveau, annee, type_, discipline, pdf):
        data = {"titre": titre, "auteur": "Auteur Test", "annee": str(annee), "type": type_, "niveau_acces": niveau}
        if discipline:
            data["discipline"] = discipline
        r = client.post("/documents", headers=headers, data=data,
                        files={"fichier": ("d.pdf", PDF, "application/pdf")} if pdf else None)
        assert r.status_code == 201, r.text
        docs.append((headers, r.json()["id_document"]))
        return r.json()["id_document"]

    def telecharger(headers, id_doc, fois=1):
        for _ in range(fois):
            assert client.get(f"/documents/{id_doc}/download", headers=headers).status_code == 200

    try:
        d1 = ajouter(ga, f"Alpha {tok}", "TELECHARGEABLE", 2001, "MEMOIRE", f"Agro{tok}", True)
        d2 = ajouter(ga, f"Beta {tok}", "TELECHARGEABLE", 2002, "MEMOIRE", f"Agro{tok}", True)
        d3 = ajouter(gb, f"Gamma {tok}", "TELECHARGEABLE", 2002, "THESE", f"Eco{tok}", True)
        d4 = ajouter(ga, f"Delta {tok}", "RESTREINT", 2001, "MEMOIRE", f"Droit{tok}", False)
        d5 = ajouter(gb, f"Epsilon {tok}", "CONSULTATION_SEULE", 2003, "MEMOIRE", None, False)
        d6 = ajouter(ga, f"=cmd {tok}", "TELECHARGEABLE", 2003, "MEMOIRE", f"Agro{tok}", True)

        telecharger(s1, d1, 3); telecharger(s2, d1, 1)           # d1 : 4
        telecharger(s1, d2, 1)                                   # d2 : 1
        telecharger(s2, d3, 2)                                   # d3 : 2
        telecharger(s1, d6, 1)                                   # d6 : 1
        # UFR A : 4 documents, 6 téléchargements, 2 étudiants ; UFR B : 2 documents, 2 téléchargements, 1 étudiant

        # ============ globales
        glob = client.get("/statistiques/globales", headers=admin).json()
        assert glob["portee"] == "GLOBALE" and glob["utilisateurs"] is not None and glob["recherches"] is not None
        assert glob["documents"]["total"] - glob0["documents"]["total"] == 6
        assert glob["telechargements"]["total"] - glob0["telechargements"]["total"] == 8
        assert glob["telechargements"]["derniers_30_jours"] - glob0["telechargements"]["derniers_30_jours"] == 8
        assert glob["utilisateurs"]["ETUDIANT"] - utilisateurs0["ETUDIANT"] == 2
        assert glob["utilisateurs"]["GESTIONNAIRE"] - utilisateurs0["GESTIONNAIRE"] == 2

        ga_glob = client.get("/statistiques/globales", headers=ga).json()
        assert ga_glob["portee"] == "UFR" and ga_glob["id_ufr"] == ufr_a and ga_glob["ufr_nom"]
        assert ga_glob["utilisateurs"] is None and ga_glob["recherches"] is None     # réservé à l'admin
        assert ga_glob["documents"]["total"] - glob_a0["documents"]["total"] == 4
        niv0, niv = glob_a0["documents"]["par_niveau_acces"], ga_glob["documents"]["par_niveau_acces"]
        assert niv["TELECHARGEABLE"] - niv0["TELECHARGEABLE"] == 3 and niv["RESTREINT"] - niv0["RESTREINT"] == 1
        assert ga_glob["telechargements"]["total"] - glob_a0["telechargements"]["total"] == 6
        assert ga_glob["telechargements"]["etudiants_distincts"] - glob_a0["telechargements"]["etudiants_distincts"] == 2
        gb_glob = client.get("/statistiques/globales", headers=gb).json()
        assert gb_glob["documents"]["total"] - glob_b0["documents"]["total"] == 2
        assert gb_glob["telechargements"]["total"] - glob_b0["telechargements"]["total"] == 2
        assert gb_glob["telechargements"]["etudiants_distincts"] - glob_b0["telechargements"]["etudiants_distincts"] == 1

        # ============ documents les plus téléchargés
        top = [d for d in client.get("/statistiques/top-documents", headers=admin, params={"limite": 100}).json()
               if tok in d["titre"]]
        assert [d["id_document"] for d in top[:2]] == [d1, d3] and [d["nb_telechargements"] for d in top[:2]] == [4, 2]
        assert {d["id_document"] for d in top[2:]} == {d2, d6} and len(top) == 4     # d4 et d5 : jamais téléchargés
        top_a = [d for d in client.get("/statistiques/top-documents", headers=ga, params={"limite": 100}).json()
                 if tok in d["titre"]]
        assert d3 not in [d["id_document"] for d in top_a] and top_a[0]["id_document"] == d1
        assert len(client.get("/statistiques/top-documents", headers=admin, params={"limite": 2}).json()) == 2

        # ============ activité par UFR
        act = client.get("/statistiques/activite-ufr", headers=admin).json()
        for id_ufr, docs_plus, tel_plus in ((ufr_a, 4, 6), (ufr_b, 2, 2)):
            assert _nb(act, "id_ufr", id_ufr, "nb_documents") - _nb(act0, "id_ufr", id_ufr, "nb_documents") == docs_plus
            assert (_nb(act, "id_ufr", id_ufr, "nb_telechargements")
                    - _nb(act0, "id_ufr", id_ufr, "nb_telechargements")) == tel_plus
        assert len(act) >= 7                                                         # toutes les UFR, même sans activité
        act_g = client.get("/statistiques/activite-ufr", headers=ga).json()
        assert len(act_g) == 1 and act_g[0]["id_ufr"] == ufr_a

        # ============ répartitions
        disc = client.get("/statistiques/repartition/discipline", headers=admin).json()
        assert _nb(disc, "libelle", f"Agro{tok}") == 3 and _nb(disc, "libelle", f"Eco{tok}") == 1
        assert _nb(disc, "libelle", f"Droit{tok}") == 1
        assert _nb(disc, "libelle", "Non renseignée") - nonrens0 == 1
        disc_a = client.get("/statistiques/repartition/discipline", headers=ga).json()
        assert _nb(disc_a, "libelle", f"Agro{tok}") == 3 and _nb(disc_a, "libelle", f"Eco{tok}") == 0
        ann = client.get("/statistiques/repartition/annee", headers=admin).json()
        for annee in ("2001", "2002", "2003"):
            assert _nb(ann, "libelle", annee) - _nb(ann0, "libelle", annee) == 2
        assert [a["libelle"] for a in ann] == sorted(a["libelle"] for a in ann)       # ordre chronologique
        ann_a = client.get("/statistiques/repartition/annee", headers=ga).json()
        assert _nb(ann_a, "libelle", "2002") >= 1
        niveaux = client.get("/statistiques/repartition/niveau_acces", headers=admin).json()
        assert {n["libelle"] for n in niveaux} <= {"TELECHARGEABLE", "CONSULTATION_SEULE", "RESTREINT"}
        assert client.get("/statistiques/repartition/type", headers=admin).status_code == 200
        r = client.get("/statistiques/repartition/couleur", headers=admin)
        assert r.status_code == 422 and r.json()["erreur"] == "ChampInvalideError"
        r = client.get("/statistiques/repartition/type; DROP TABLE documents", headers=admin)
        assert r.status_code == 422                                                   # liste blanche

        # ============ documents restreints
        rest = [d["id_document"] for d in client.get("/statistiques/documents-restreints", headers=admin).json()]
        assert d4 in rest and d5 not in rest
        assert d4 in [d["id_document"] for d in client.get("/statistiques/documents-restreints", headers=ga).json()]
        assert d4 not in [d["id_document"] for d in client.get("/statistiques/documents-restreints", headers=gb).json()]

        # ============ recherches sans résultat (journal alimenté par la recherche de l'étudiant)
        for _ in range(2):
            assert client.get("/documents/recherche", headers=s1, params={"q": f"{tok} qzx"}).json()["total"] == 0
        assert client.get("/documents/recherche", headers=s1, params={"q": tok}).json()["total"] >= 1
        sans = client.get("/statistiques/recherches-sans-resultat", headers=admin).json()
        assert _nb(sans, "requete", f"q={tok} qzx", "nb_fois") == 2
        assert f"q={tok}" not in [x["requete"] for x in sans]                         # une recherche réussie n'y figure pas
        assert client.get("/statistiques/recherches-sans-resultat", headers=ga).status_code == 403

        # ============ droits
        assert client.get("/statistiques/globales", headers=s1).status_code == 403
        assert client.get("/statistiques/top-documents", headers=s1).status_code == 403
        assert client.get("/statistiques/globales").status_code == 401
        r = client.get("/statistiques/globales", headers=ga, params={"id_ufr": ufr_b})
        assert r.status_code == 403 and r.json()["erreur"] == "AccesRefuseError"
        assert client.get("/statistiques/globales", headers=ga, params={"id_ufr": ufr_a}).status_code == 200
        r = client.get("/statistiques/globales", headers=admin, params={"id_ufr": 99999})
        assert r.status_code == 404 and r.json()["erreur"] == "UfrIntrouvableError"

        # ============ export CSV
        r = client.get("/statistiques/export/top-documents", headers=admin)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert "top-documents.csv" in r.headers["content-disposition"]
        assert r.content.startswith(b"\xef\xbb\xbf")                                  # BOM UTF-8 pour Excel
        lignes = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
        assert lignes[0] == ["id_document", "titre", "auteur", "ufr_nom", "nb_telechargements"]
        titres = [l[1] for l in lignes[1:] if tok in l[1]]
        assert f"Alpha {tok}" in titres
        assert f"'=cmd {tok}" in titres and f"=cmd {tok}" not in titres               # formule neutralisée
        assert not any(l[1].startswith("=") for l in lignes[1:])
        exp_a = list(csv.reader(io.StringIO(client.get("/statistiques/export/activite-ufr", headers=ga)
                                            .content.decode("utf-8-sig")), delimiter=";"))
        assert len(exp_a) == 2 and exp_a[1][0] == str(ufr_a)                          # en-tête + sa seule UFR
        for jeu in ("repartition-discipline", "repartition-annee", "documents-restreints"):
            assert client.get(f"/statistiques/export/{jeu}", headers=admin).status_code == 200
        exp_sans = client.get("/statistiques/export/recherches-sans-resultat", headers=admin).content.decode("utf-8-sig")
        assert f"q={tok} qzx" in exp_sans
        assert client.get("/statistiques/export/recherches-sans-resultat", headers=ga).status_code == 403
        r = client.get("/statistiques/export/inconnu", headers=admin)
        assert r.status_code == 422 and r.json()["erreur"] == "ChampInvalideError"
        assert client.get("/statistiques/export/top-documents", headers=s1).status_code == 403
    finally:
        for headers, id_doc in docs:
            client.delete(f"/documents/{id_doc}", headers=headers)
        for uid in (id_ga, id_gb, id_s1, id_s2):
            client.delete(f"/users/{uid}", headers=admin)
        conn = ouvrir_connexion()
        try:
            conn.execute("DELETE FROM recherches WHERE requete LIKE %s", (f"%{tok}%",))
            conn.commit()
        finally:
            conn.close()
