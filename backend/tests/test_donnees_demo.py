"""Programme de données de démonstration : création, cohérence avec l'application, suppression propre (MySQL requis)."""
import random
import re
import uuid
from datetime import datetime, timedelta

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import ouvrir_connexion
from app.main import app
from scripts import donnees_demo as demo



def _base_disponible() -> bool:
    try:
        ouvrir_connexion().close()
        return True
    except pymysql.MySQLError:
        return False


pytestmark = pytest.mark.skipif(not _base_disponible(), reason="MySQL indisponible")


# ------------------------------------------------------------------ le PDF fabriqué est un vrai PDF
def test_pdf_minimal_est_structurellement_valide():
    pdf = demo.pdf_minimal("Titre avec (parenthèses) et \\ accents éèà", "Awa Diop", 2024, "Agronomie", "UFR Test")
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    debut_xref = int(re.search(rb"startxref\n(\d+)\n", pdf).group(1))
    assert pdf[debut_xref:debut_xref + 4] == b"xref"
    lignes = pdf[debut_xref:].split(b"\n")
    nb_objets = int(lignes[1].split()[1])
    assert nb_objets == 6
    for numero in range(1, nb_objets):                 # chaque entrée de la table pointe bien vers « N 0 obj »
        entree = lignes[2 + numero]
        assert len(entree) + 1 == 20
        position = int(entree[:10])
        assert pdf[position:].startswith(b"%d 0 obj" % numero)


def test_pdf_minimal_est_lisible_par_un_lecteur_pdf():
    pypdf = pytest.importorskip("pypdf")
    import io
    lecteur = pypdf.PdfReader(io.BytesIO(demo.pdf_minimal("Étude de l'irrigation", "Awa Diop", 2024, "Agronomie", "UFR Test")), strict=True)
    assert len(lecteur.pages) == 1 and "irrigation" in lecteur.pages[0].extract_text()


# ------------------------------------------------------------------ charger / vérifier / supprimer
def _compteurs(conn):
    return conn.execute(
        "SELECT (SELECT COUNT(*) FROM utilisateurs) AS utilisateurs, (SELECT COUNT(*) FROM documents) AS documents, "
        "(SELECT COUNT(*) FROM telechargements) AS telechargements, (SELECT COUNT(*) FROM recherches) AS recherches, "
        "(SELECT COUNT(*) FROM ufr) AS ufr").fetchone()


def test_charger_verifier_et_supprimer_sans_toucher_au_reste(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    conn = ouvrir_connexion()
    try:
        if demo.etat(conn)["gestionnaires"]:
            pytest.skip("Des données de démonstration sont déjà chargées : ce test ne les touche pas.")

        with TestClient(app) as client:
            admin = {"Authorization": "Bearer " + client.post("/auth/login", json={
                "email": settings.admin_email, "mot_de_passe": settings.admin_password}).json()["access_token"]}

            # --- des données « réelles » créées avant : elles doivent survivre à tout
            tok = uuid.uuid4().hex[:6]
            email_reel = f"reel.{tok}@ugb.edu.sn"
            ufr_id = client.get("/ufr", headers=admin).json()[0]["id_ufr"]
            id_reel = client.post("/users/gestionnaires", headers=admin, json={
                "nom": "Reel", "prenom": "Vrai", "email": email_reel, "mot_de_passe": "Motdepasse1", "id_ufr": ufr_id}).json()["id_utilisateur"]
            jeton_reel = {"Authorization": "Bearer " + client.post("/auth/login", json={
                "email": email_reel, "mot_de_passe": "Motdepasse1"}).json()["access_token"]}
            id_doc_reel = client.post("/documents", headers=jeton_reel, data={
                "titre": f"Document reel {tok}", "auteur": "Auteur Reel", "annee": "2024", "type": "MEMOIRE",
                "niveau_acces": "CONSULTATION_SEULE"}).json()["id_document"]
            conn.commit()    # rafraîchit la vue de cette connexion : elle doit voir ce que l'application vient de créer
            avant = _compteurs(conn)

            try:
                # ========== chargement
                resultat = demo.charger(conn, rng=random.Random(1))
                nb_gest = len(resultat["gestionnaires"])
                assert nb_gest >= 1 and len(resultat["etudiants"]) == demo.NB_ETUDIANTS
                assert resultat["documents"] == 6 * nb_gest
                apres = _compteurs(conn)
                assert apres["utilisateurs"] - avant["utilisateurs"] == nb_gest + demo.NB_ETUDIANTS
                assert apres["documents"] - avant["documents"] == resultat["documents"]
                assert apres["telechargements"] - avant["telechargements"] == demo.NB_TELECHARGEMENTS
                assert apres["ufr"] == avant["ufr"]

                # tous les comptes de démonstration sont reconnaissables
                assert conn.execute("SELECT COUNT(*) AS n FROM utilisateurs WHERE email LIKE 'demo.%%@ugb.edu.sn'").fetchone()["n"] \
                    == nb_gest + demo.NB_ETUDIANTS

                # niveaux d'accès variés, PDF réels sur disque
                niveaux = {r["niveau_acces"]: r["n"] for r in conn.execute(
                    "SELECT niveau_acces, COUNT(*) AS n FROM documents WHERE cree_par IN (SELECT id_utilisateur FROM utilisateurs WHERE email LIKE 'demo.%%') GROUP BY niveau_acces").fetchall()}
                assert niveaux["RESTREINT"] == nb_gest and niveaux["CONSULTATION_SEULE"] >= nb_gest and niveaux["TELECHARGEABLE"] >= 3 * nb_gest
                fichiers = list(tmp_path.glob("*.pdf"))
                assert len(fichiers) == resultat["documents"] and all(f.read_bytes().startswith(b"%PDF-") for f in fichiers)

                # téléchargements : seulement des documents téléchargeables, sur 90 jours, avec des documents très demandés
                lignes = conn.execute(
                    "SELECT t.id_document, t.date_telechargement, d.niveau_acces FROM telechargements t "
                    "JOIN documents d ON d.id_document = t.id_document "
                    "WHERE t.id_utilisateur IN (SELECT id_utilisateur FROM utilisateurs WHERE email LIKE 'demo.%%')").fetchall()
                assert len(lignes) == demo.NB_TELECHARGEMENTS and {l["niveau_acces"] for l in lignes} == {"TELECHARGEABLE"}
                maintenant = datetime.now()
                assert all(maintenant - timedelta(days=demo.JOURS_HISTORIQUE + 1) <= l["date_telechargement"] <= maintenant + timedelta(minutes=1) for l in lignes)
                par_doc = {}
                for l in lignes:
                    par_doc[l["id_document"]] = par_doc.get(l["id_document"], 0) + 1
                assert len(par_doc) >= 8 and max(par_doc.values()) >= 3 * min(par_doc.values())

                # recherches : 7 requêtes sans résultat, les autres avec des résultats
                zeros = {r["requete"] for r in conn.execute("SELECT DISTINCT requete FROM recherches WHERE nb_resultats = 0 AND requete IN (%s)" % ",".join(["%s"] * 7),
                                                           [demo._requete_journal(c) for c in demo.RECHERCHES_SANS_RESULTAT]).fetchall()}
                assert len(zeros) == 7

                # ========== cohérence avec l'application
                fixe = {"email": f"demo.gestionnaire.{demo.THEMES[0]['cle']}@ugb.edu.sn"}
                gest_demo = resultat["gestionnaires"][0]
                assert client.post("/auth/login", json={"email": gest_demo["email"], "mot_de_passe": demo.MOT_DE_PASSE_DEMO}).status_code == 200
                e = resultat["etudiants"][0]
                r = client.post("/auth/login-etudiant", json={"prenom": e["prenom"], "nom": e["nom"], "email": e["email"], "code_etudiant": e["code"]})
                assert r.status_code == 200
                etu = {"Authorization": "Bearer " + r.json()["access_token"]}

                # un document sous embargo n'est jamais trouvé ; les autres le sont
                assert client.get("/documents/recherche", headers=etu, params={"q": "érosion"}).json()["total"] == 0
                trouves = client.get("/documents/recherche", headers=etu, params={"q": "irrigation", "taille": 50}).json()
                assert trouves["total"] >= 1 and all(d["niveau_acces"] != "RESTREINT" for d in trouves["resultats"])

                # le nombre de résultats enregistré par le programme == celui que renvoie vraiment la recherche
                a_verifier = [c for c in demo.RECHERCHES_AVEC_RESULTATS if set(c) == {"q"}][:6]
                assert len(a_verifier) >= 5
                for criteres in a_verifier:
                    enregistre = conn.execute("SELECT nb_resultats FROM recherches WHERE requete = %s AND nb_resultats > 0 LIMIT 1",
                                              (demo._requete_journal(criteres),)).fetchone()
                    if enregistre:   # (la recherche peut avoir été écartée si elle ne donnait rien)
                        reel = client.get("/documents/recherche", headers=etu, params={"q": criteres["q"]}).json()["total"]
                        assert enregistre["nb_resultats"] == reel, criteres

                # les statistiques sont enfin bien remplies
                glob = client.get("/statistiques/globales", headers=admin).json()
                assert glob["telechargements"]["total"] >= demo.NB_TELECHARGEMENTS and glob["telechargements"]["derniers_30_jours"] > 50
                assert glob["recherches"]["sans_resultat"] >= 20
                assert len(client.get("/statistiques/top-documents", headers=admin, params={"limite": 8}).json()) == 8
                sans = {x["requete"] for x in client.get("/statistiques/recherches-sans-resultat", headers=admin, params={"limite": 50}).json()}
                assert "q=chatbot" in sans and "q=blockchain" in sans
                activite = client.get("/statistiques/activite-ufr", headers=admin).json()
                assert sum(1 for a in activite if a["nb_telechargements"] > 0) >= nb_gest

                # ========== un deuxième chargement est refusé
                with pytest.raises(demo.DejaCharge):
                    demo.charger(conn, rng=random.Random(2))
                assert _compteurs(conn)["documents"] == apres["documents"]

                # ========== suppression : on revient exactement à l'état d'avant
                supprime = demo.supprimer(conn)
                assert supprime == {"gestionnaires": nb_gest, "etudiants": demo.NB_ETUDIANTS, "documents": resultat["documents"]}
                assert _compteurs(conn) == avant
                assert list(tmp_path.glob("*.pdf")) == []
                assert demo.supprimer(conn) == {"gestionnaires": 0, "etudiants": 0, "documents": 0}   # rien à supprimer = pas d'erreur

                # ce qui existait avant est intact (compte réel, son document, administrateur, étudiant d'exemple du script SQL)
                assert conn.execute("SELECT COUNT(*) AS n FROM utilisateurs WHERE id_utilisateur = %s", (id_reel,)).fetchone()["n"] == 1
                assert conn.execute("SELECT COUNT(*) AS n FROM documents WHERE id_document = %s", (id_doc_reel,)).fetchone()["n"] == 1
                assert conn.execute("SELECT COUNT(*) AS n FROM utilisateurs WHERE email = %s", (settings.admin_email,)).fetchone()["n"] == 1
            finally:
                if demo.etat(conn)["gestionnaires"]:
                    demo.supprimer(conn)
                client.delete(f"/documents/{id_doc_reel}", headers=jeton_reel)
                client.delete(f"/users/{id_reel}", headers=admin)
    finally:
        conn.close()
