"""Données de démonstration pour l'application (ENTIÈREMENT FICTIVES).

À lancer depuis le dossier backend, environnement virtuel activé :

    python scripts/donnees_demo.py charger      crée les données (gestionnaires, étudiants, documents, téléchargements...)
    python scripts/donnees_demo.py supprimer    supprime uniquement les données de démonstration
    python scripts/donnees_demo.py etat         indique si les données de démonstration sont présentes

Ce qui est créé est reconnaissable : tous les comptes de démonstration ont un email « demo.xxx@ugb.edu.sn ».
Les comptes et documents que tu as créés toi-même ne sont jamais modifiés ni supprimés.
"""
import os
import random
import re
import sys
import textwrap
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

DOSSIER_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOSSIER_BACKEND))

from app.database import ouvrir_connexion  # noqa: E402
from app.fichiers import enregistrer_pdf, supprimer_pdf  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.validation import normaliser_mots_cles  # noqa: E402

MOT_DE_PASSE_DEMO = "Demo2026!"
MOTIF_EMAIL_DEMO = "demo.%@ugb.edu.sn"
JOURS_HISTORIQUE = 90
NB_ETUDIANTS = 24
NB_TELECHARGEMENTS = 320

PRENOMS = ["Awa", "Fatou", "Mariama", "Aminata", "Khady", "Ndeye", "Rokhaya", "Coumba", "Moussa", "Cheikh", "Ibrahima",
           "Ousmane", "Mamadou", "Abdoulaye", "Pape", "Samba"]
NOMS = ["Ndiaye", "Diallo", "Sarr", "Faye", "Mbaye", "Thiam", "Cisse", "Gueye", "Sow", "Ba", "Diouf", "Seck", "Fall", "Sy",
        "Samb", "Mendy"]
ENCADRANTS = ["Pr Alioune Diouf", "Dr Mame Diarra Seck", "Pr Souleymane Gueye", "Dr Ndeye Fatou Samb", "Pr Mamadou Lamine Sy",
              "Dr Rokhaya Badji", "Pr Abdoulaye Dione", "Dr Coumba Mendy"]

# Chaque thème correspond à une UFR (repérée par un mot de son nom) : gestionnaire + 6 documents fictifs.
# (titre, mots-clés, discipline)
THEMES = [
    {"cle": "agro", "motif": "agronomi", "gestionnaire": ("Cheikh", "Sarr"), "documents": [
        ("Effet de l'irrigation goutte-à-goutte sur le rendement de l'oignon", "irrigation, oignon, rendement", "Agronomie"),
        ("Valorisation des sous-produits de la pêche en alimentation animale", "sous-produits, pêche, alimentation animale", "Aquaculture"),
        ("Élevage de tilapia en cages flottantes : performances de croissance", "tilapia, aquaculture, croissance", "Aquaculture"),
        ("Transformation du mil en farines infantiles : qualité nutritionnelle", "mil, farine, nutrition", "Technologies alimentaires"),
        ("Gestion de la fertilité des sols dans les périmètres rizicoles", "fertilité des sols, riz, périmètre irrigué", "Agronomie"),
        ("Conservation des mangues par séchage solaire", "mangue, séchage solaire, conservation", "Technologies alimentaires")]},
    {"cle": "sante", "motif": "sante", "gestionnaire": ("Khady", "Mbaye"), "documents": [
        ("Facteurs associés à la couverture vaccinale des enfants de moins de cinq ans", "vaccination, enfants, couverture", "Santé publique"),
        ("Qualité de l'accueil et satisfaction des patients dans un centre de santé de district", "qualité des soins, satisfaction, centre de santé", "Santé publique"),
        ("Prévalence de l'hypertension artérielle chez les adultes en milieu urbain", "hypertension, prévalence, adultes", "Médecine"),
        ("Connaissances des mères sur la nutrition du nourrisson", "nutrition, nourrisson, mères", "Santé publique"),
        ("Usage des plantes médicinales dans la prise en charge du paludisme", "plantes médicinales, paludisme, pharmacopée", "Pharmacie"),
        ("Organisation de la chaîne d'approvisionnement des médicaments essentiels", "médicaments, approvisionnement, logistique", "Pharmacie")]},
    {"cle": "eco", "motif": "economi", "gestionnaire": ("Ibrahima", "Thiam"), "documents": [
        ("Impact du microcrédit sur l'activité des commerçantes de marché", "microcrédit, commerce, femmes", "Économie"),
        ("Analyse de la rentabilité des petites exploitations maraîchères", "rentabilité, maraîchage, exploitation", "Économie"),
        ("Stratégies de fidélisation de la clientèle dans la téléphonie mobile", "fidélisation, clientèle, marketing", "Gestion"),
        ("Gouvernance et performance financière des collectivités locales", "gouvernance, finances locales, performance", "Finance"),
        ("Rôle des transferts d'argent des migrants dans le financement du logement", "transferts, migrants, logement", "Économie"),
        ("Étude de la chaîne de valeur de la tomate industrielle", "chaîne de valeur, tomate, filière", "Économie")]},
    {"cle": "droit", "motif": "juridique", "gestionnaire": ("Aminata", "Faye"), "documents": [
        ("La protection des données personnelles dans les services de paiement mobile", "données personnelles, paiement mobile, protection", "Droit privé"),
        ("Contentieux foncier et sécurisation des droits des exploitants agricoles", "foncier, contentieux, agriculteurs", "Droit privé"),
        ("Décentralisation et compétences des collectivités en matière d'éducation", "décentralisation, collectivités, éducation", "Droit public"),
        ("La participation des femmes à la vie politique locale", "participation politique, femmes, élections locales", "Science politique"),
        ("Le droit du travail face à l'économie informelle", "droit du travail, informel, protection sociale", "Droit privé"),
        ("La médiation comme mode alternatif de règlement des conflits commerciaux", "médiation, conflits, commerce", "Droit privé")]},
    {"cle": "lettres", "motif": "lettres", "gestionnaire": ("Mariama", "Diallo"), "documents": [
        ("Les migrations saisonnières dans la vallée du fleuve au XXe siècle", "migrations, histoire sociale, fleuve", "Histoire"),
        ("Représentations de la femme dans le roman sénégalais contemporain", "roman, genre, littérature", "Lettres modernes"),
        ("Alternance codique wolof-français chez les jeunes citadins", "wolof, français, sociolinguistique", "Linguistique"),
        ("Urbanisation et mutations de l'espace périurbain de Saint-Louis", "urbanisation, périurbain, aménagement", "Géographie"),
        ("Les associations de quartier et la gestion collective des déchets", "associations, déchets, quartier", "Sociologie"),
        ("L'oralité et la transmission des savoirs dans les contes traditionnels", "oralité, contes, transmission", "Lettres modernes")]},
    {"cle": "civ", "motif": "civilisations", "gestionnaire": ("Moussa", "Gueye"), "documents": [
        ("Usage des réseaux sociaux par les jeunes pour s'informer sur l'actualité locale", "réseaux sociaux, information, jeunes", "Communication"),
        ("La radio communautaire et le développement local", "radio, communauté, développement", "Communication"),
        ("Le patrimoine architectural de l'île et sa valorisation touristique", "patrimoine, architecture, tourisme", "Arts"),
        ("Les festivals de jazz comme vecteur d'attractivité culturelle", "jazz, festival, culture", "Arts"),
        ("Dialogue interreligieux et cohésion sociale en milieu universitaire", "interreligieux, cohésion sociale, université", "Civilisations"),
        ("La communication de crise des institutions publiques lors des inondations", "communication de crise, inondations, institutions", "Communication")]},
    {"cle": "sat", "motif": "appliquees", "gestionnaire": ("Ousmane", "Ndoye"), "documents": [
        ("Conception d'un système d'information pour la gestion des stocks d'une coopérative", "système d'information, gestion de stock, base de données", "Informatique"),
        ("Application mobile de suivi de la qualité de l'eau en zone rurale", "application mobile, eau, capteurs", "Informatique"),
        ("Détection de fraudes par apprentissage automatique sur des transactions de mobile money", "apprentissage automatique, fraude, mobile money", "Informatique"),
        ("Modélisation de la propagation d'une épidémie dans une population urbaine", "modélisation, épidémie, équations différentielles", "Mathématiques appliquées"),
        ("Dimensionnement d'une installation photovoltaïque pour un centre de santé", "énergie solaire, photovoltaïque, dimensionnement", "Physique"),
        ("Étude de l'érosion des berges et solutions de protection dans la vallée du fleuve", "érosion, berges, hydraulique", "Génie civil")]},
]

# (critères de recherche) -> la requête est enregistrée dans le journal comme le fait l'application
RECHERCHES_AVEC_RESULTATS = [
    {"q": "irrigation"}, {"q": "santé"}, {"q": "eau"}, {"q": "femmes"}, {"q": "communication"},
    {"q": "mobile"}, {"q": "nutrition"}, {"q": "droit"}, {"q": "données"}, {"q": "riz"}, {"q": "tilapia"}, {"q": "wolof"},
    {"annee": 2024}, {"annee": 2025}, {"discipline": "Droit"}, {"discipline": "Informatique"}, {"type": "THESE"},
    {"mot_cle": "irrigation"}, {"q": "agricoles"},
]
RECHERCHES_SANS_RESULTAT = [
    {"q": "blockchain"}, {"q": "chatbot"}, {"q": "drone agricole"}, {"q": "cryptomonnaie"}, {"q": "réalité virtuelle"},
    {"q": "intelligence artificielle"}, {"q": "blockchain", "annee": 2025},
]
COLONNES_TEXTE = ("titre", "auteur", "encadrant", "discipline", "mots_cles", "resume")


class DejaCharge(Exception):
    """Les données de démonstration existent déjà."""


# ------------------------------------------------------------------ outils
def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def _slug(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _sans_accents(texte).lower())


def pdf_minimal(titre, auteur, annee, discipline, ufr) -> bytes:
    """Fabrique un vrai petit PDF d'une page (lisible par tous les lecteurs), sans aucune bibliothèque."""
    lignes = textwrap.wrap(titre, 58) + ["", f"Auteur : {auteur}", f"Annee : {annee}", f"Discipline : {discipline}",
                                          f"UFR : {ufr}", "", "Document fictif genere pour la demonstration",
                                          "de l'application (aucune donnee reelle)."]

    def echapper(t):
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    flux = "BT /F1 16 Tf 56 780 Td 22 TL\n" + "\n".join(f"({echapper(l)}) '" for l in lignes) + "\nET"
    flux_octets = flux.encode("cp1252", errors="replace")
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(flux_octets) + flux_octets + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    positions = []
    for numero, contenu in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += b"%d 0 obj\n" % numero + contenu + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += b"xref\n0 %d\n" % (len(objets) + 1) + b"0000000000 65535 f \n"
    for position in positions:
        sortie += b"%010d 00000 n \n" % position
    sortie += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objets) + 1, debut_xref)
    return bytes(sortie)


def _resume(titre, discipline, type_document, rng) -> str:
    sujet = titre[0].lower() + titre[1:]
    sujet = sujet.rstrip(".")
    ce_travail = "Cette thèse" if type_document == "THESE" else "Ce mémoire"
    modeles = [
        f"{ce_travail} s'intéresse au thème suivant : {sujet}. Après une revue de la littérature en {discipline.lower()}, "
        f"l'étude présente la méthodologie retenue, expose les principaux résultats obtenus sur le terrain et propose "
        f"des recommandations pratiques.",
        f"{ce_travail} analyse la question suivante : {sujet}. L'auteur s'appuie sur une enquête de terrain et sur des "
        f"données collectées auprès des acteurs concernés ({discipline.lower()}), puis discute les limites de l'étude "
        f"et les pistes de recherche futures.",
        f"À partir d'une démarche mêlant revue documentaire et observation de terrain, {ce_travail.lower()} étudie : "
        f"{sujet}. Les résultats mettent en évidence des contraintes importantes et ouvrent des perspectives "
        f"d'amélioration dans le champ de la {discipline.lower()}.",
    ]
    return rng.choice(modeles)


def _compter(conn, criteres) -> int:
    """Nombre de documents visibles par un étudiant pour ces critères (mêmes règles que la recherche de l'application)."""
    conditions, params = ["niveau_acces <> 'RESTREINT'"], []
    for mot in (criteres.get("q") or "").split():
        conditions.append("(" + " OR ".join(f"{c} LIKE %s" for c in COLONNES_TEXTE) + ")")
        params += [f"%{mot}%"] * len(COLONNES_TEXTE)
    if "annee" in criteres:
        conditions.append("annee = %s"); params.append(criteres["annee"])
    if "discipline" in criteres:
        conditions.append("discipline LIKE %s"); params.append(f"%{criteres['discipline']}%")
    if "type" in criteres:
        conditions.append("type = %s"); params.append(criteres["type"])
    if "mot_cle" in criteres:
        conditions.append("CONCAT(', ', mots_cles, ', ') LIKE %s"); params.append(f"%, {criteres['mot_cle']}, %")
    return int(conn.execute("SELECT COUNT(*) AS n FROM documents WHERE " + " AND ".join(conditions), params).fetchone()["n"])


def _requete_journal(criteres) -> str:
    return " | ".join(f"{cle}={criteres[cle]}" for cle in ("q", "annee", "discipline", "mot_cle", "type") if cle in criteres)


def _date_recente(rng, maintenant) -> datetime:
    """Plus de dates récentes que de dates anciennes, sur les JOURS_HISTORIQUE derniers jours, en journée."""
    jours = int(rng.triangular(0, JOURS_HISTORIQUE, 0))
    jour = (maintenant - timedelta(days=jours)).replace(hour=rng.randint(8, 21), minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)
    return min(jour, maintenant)


# ------------------------------------------------------------------ chargement
def charger(conn, rng=None, maintenant=None) -> dict:
    rng = rng or random.Random(2026)
    maintenant = maintenant or datetime.now()
    deja = conn.execute("SELECT COUNT(*) AS n FROM utilisateurs WHERE email LIKE %s", (MOTIF_EMAIL_DEMO,)).fetchone()["n"]
    if deja:
        raise DejaCharge("Les données de démonstration existent déjà. Lance d'abord : python scripts/donnees_demo.py supprimer")

    fichiers_crees = []
    try:
        # --- UFR concernées (repérées par un mot de leur nom)
        ufrs = conn.execute("SELECT id_ufr, nom FROM ufr ORDER BY id_ufr").fetchall()
        affectations = []   # (ufr, thème)
        themes_libres = list(THEMES)
        for ufr in ufrs:
            nom = _sans_accents(ufr["nom"]).lower()
            theme = next((t for t in themes_libres if t["motif"] in nom), None)
            if theme:
                themes_libres.remove(theme)
                affectations.append((ufr, theme))
        if not affectations:
            raise RuntimeError("Aucune UFR connue n'a été trouvée : importe d'abord db/02_seed.sql.")

        # --- gestionnaires (un par UFR)
        gestionnaires = {}
        for ufr, theme in affectations:
            prenom, nom = theme["gestionnaire"]
            email = f"demo.gestionnaire.{theme['cle']}@ugb.edu.sn"
            curseur = conn.execute(
                "INSERT INTO utilisateurs (nom, prenom, email, role, id_ufr, mot_de_passe_hash) VALUES (%s, %s, %s, 'GESTIONNAIRE', %s, %s)",
                (nom, prenom, email, ufr["id_ufr"], hash_password(MOT_DE_PASSE_DEMO)))
            gestionnaires[ufr["id_ufr"]] = {"id": curseur.lastrowid, "email": email, "prenom": prenom, "nom": nom}

        # --- étudiants
        combinaisons = [(p, n) for p in PRENOMS for n in NOMS]
        rng.shuffle(combinaisons)
        etudiants, emails_pris = [], set()
        for prenom, nom in combinaisons:
            if len(etudiants) == NB_ETUDIANTS:
                break
            email = f"demo.{_slug(prenom)}.{_slug(nom)}@ugb.edu.sn"
            if email in emails_pris:
                continue
            emails_pris.add(email)
            code = f"DMO2026{len(etudiants) + 1:03d}"
            curseur = conn.execute(
                "INSERT INTO utilisateurs (nom, prenom, email, role, code_etudiant) VALUES (%s, %s, %s, 'ETUDIANT', %s)",
                (nom, prenom, email, code))
            etudiants.append({"id": curseur.lastrowid, "prenom": prenom, "nom": nom, "email": email, "code": code})

        # --- documents
        documents = []
        annee_max = maintenant.year
        for ufr, theme in affectations:
            # 3 documents toujours téléchargeables, le 4e parfois en consultation seule, puis 1 consultation et 1 embargo
            niveaux = ["TELECHARGEABLE"] * 3 + [rng.choice(["TELECHARGEABLE", "CONSULTATION_SEULE"]), "CONSULTATION_SEULE", "RESTREINT"]
            for (titre, mots_cles, discipline), niveau in zip(theme["documents"], niveaux):
                type_document = "THESE" if rng.random() < 0.25 else "MEMOIRE"
                annee = rng.choices(range(annee_max - 7, annee_max + 1), weights=[1, 2, 2, 3, 3, 4, 4, 2])[0]
                auteur = f"{rng.choice(PRENOMS)} {rng.choice(NOMS)}"
                chemin = enregistrer_pdf(pdf_minimal(titre, auteur, annee, discipline, ufr["nom"]))
                fichiers_crees.append(chemin)
                cree_le = maintenant - timedelta(days=rng.randint(JOURS_HISTORIQUE + 10, 420))
                curseur = conn.execute(
                    "INSERT INTO documents (titre, auteur, encadrant, annee, type, id_ufr, discipline, resume, mots_cles, "
                    "chemin_pdf, niveau_acces, cree_par, cree_le) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (titre, auteur, rng.choice(ENCADRANTS), annee, type_document, ufr["id_ufr"], discipline,
                     _resume(titre, discipline, type_document, rng), normaliser_mots_cles(mots_cles), chemin, niveau,
                     gestionnaires[ufr["id_ufr"]]["id"], cree_le))
                documents.append({"id": curseur.lastrowid, "niveau": niveau})

        # --- téléchargements : quelques documents très demandés, d'autres presque jamais (courbe réaliste)
        telechargeables = [d for d in documents if d["niveau"] == "TELECHARGEABLE"]
        rng.shuffle(telechargeables)
        poids = [1 / (rang + 1) ** 0.9 for rang in range(len(telechargeables))]
        for _ in range(NB_TELECHARGEMENTS):
            document = rng.choices(telechargeables, weights=poids)[0]
            conn.execute("INSERT INTO telechargements (id_utilisateur, id_document, date_telechargement) VALUES (%s, %s, %s)",
                         (rng.choice(etudiants)["id"], document["id"], _date_recente(rng, maintenant)))

        # --- recherches (le nombre de résultats est calculé sur les vrais documents)
        nb_recherches = 0
        prevues = ([(c, rng.randint(2, 6), True) for c in RECHERCHES_AVEC_RESULTATS]
                   + [(c, rng.randint(2, 7), False) for c in RECHERCHES_SANS_RESULTAT])
        for criteres, repetitions, doit_reussir in prevues:
            total = _compter(conn, criteres)
            if (total > 0) != doit_reussir:    # ex. un mot « sans résultat » qui existerait dans tes vrais documents
                continue
            for _ in range(repetitions):
                conn.execute("INSERT INTO recherches (id_utilisateur, requete, nb_resultats, date_recherche) VALUES (%s, %s, %s, %s)",
                             (rng.choice(etudiants)["id"], _requete_journal(criteres), total, _date_recente(rng, maintenant)))
                nb_recherches += 1

        conn.commit()
    except Exception:
        conn.rollback()
        for chemin in fichiers_crees:
            supprimer_pdf(chemin)
        raise

    return {
        "gestionnaires": list(gestionnaires.values()), "etudiants": etudiants, "documents": len(documents),
        "telechargements": NB_TELECHARGEMENTS, "recherches": nb_recherches,
    }


# ------------------------------------------------------------------ suppression
def _ids_demo(conn):
    lignes = conn.execute("SELECT id_utilisateur, role FROM utilisateurs WHERE email LIKE %s AND role <> 'ADMIN'", (MOTIF_EMAIL_DEMO,)).fetchall()
    return ([l["id_utilisateur"] for l in lignes if l["role"] == "GESTIONNAIRE"],
            [l["id_utilisateur"] for l in lignes if l["role"] == "ETUDIANT"])


def etat(conn) -> dict:
    gestionnaires, etudiants = _ids_demo(conn)
    documents = 0
    if gestionnaires:
        documents = conn.execute("SELECT COUNT(*) AS n FROM documents WHERE cree_par IN (%s)" % ",".join(["%s"] * len(gestionnaires)),
                                 gestionnaires).fetchone()["n"]
    return {"gestionnaires": len(gestionnaires), "etudiants": len(etudiants), "documents": documents}


def supprimer(conn) -> dict:
    """Supprime les comptes « demo.* », les documents qu'ils ont créés, leurs téléchargements, leurs recherches et leurs PDF."""
    gestionnaires, etudiants = _ids_demo(conn)
    if not gestionnaires and not etudiants:
        return {"gestionnaires": 0, "etudiants": 0, "documents": 0}
    fichiers, nb_documents = [], 0
    if gestionnaires:
        marques = ",".join(["%s"] * len(gestionnaires))
        docs = conn.execute(f"SELECT id_document, chemin_pdf FROM documents WHERE cree_par IN ({marques})", gestionnaires).fetchall()
        fichiers, nb_documents = [d["chemin_pdf"] for d in docs if d["chemin_pdf"]], len(docs)
    if etudiants:   # avant les comptes : sinon le lien avec leurs recherches serait perdu
        conn.execute("DELETE FROM recherches WHERE id_utilisateur IN (%s)" % ",".join(["%s"] * len(etudiants)), etudiants)
    if gestionnaires:
        conn.execute("DELETE FROM documents WHERE cree_par IN (%s)" % ",".join(["%s"] * len(gestionnaires)), gestionnaires)
    tous = gestionnaires + etudiants
    conn.execute("DELETE FROM utilisateurs WHERE id_utilisateur IN (%s)" % ",".join(["%s"] * len(tous)), tous)
    conn.commit()
    for chemin in fichiers:
        supprimer_pdf(chemin)
    return {"gestionnaires": len(gestionnaires), "etudiants": len(etudiants), "documents": nb_documents}


# ------------------------------------------------------------------ ligne de commande
def principal(arguments) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")   # évite un plantage sur la console Windows
    os.chdir(DOSSIER_BACKEND)                      # le dossier « uploads » doit être le même que celui du serveur
    commande = arguments[0] if arguments else ""
    if commande not in ("charger", "supprimer", "etat"):
        print(__doc__)
        return 1
    try:
        conn = ouvrir_connexion()
    except Exception as erreur:
        print("Impossible de se connecter à MySQL. Vérifie que WAMP est vert et que backend\\.env est correct.")
        print("Détail :", erreur)
        return 1
    try:
        if commande == "etat":
            e = etat(conn)
            print(f"Données de démonstration : {e['gestionnaires']} gestionnaires, {e['etudiants']} étudiants, {e['documents']} documents.")
            return 0
        if commande == "supprimer":
            e = etat(conn)
            if not e["gestionnaires"] and not e["etudiants"]:
                print("Aucune donnée de démonstration à supprimer.")
                return 0
            print(f"Seront supprimés : {e['gestionnaires']} gestionnaires, {e['etudiants']} étudiants, {e['documents']} documents "
                  "(avec leurs téléchargements et leurs recherches). Tes autres données ne seront pas touchées.")
            if "--oui" not in arguments and input("Tape O pour confirmer : ").strip().lower() not in ("o", "oui"):
                print("Annulé.")
                return 0
            s = supprimer(conn)
            print(f"Terminé : {s['gestionnaires']} gestionnaires, {s['etudiants']} étudiants et {s['documents']} documents supprimés.")
            return 0
        try:
            resultat = charger(conn)
        except DejaCharge as erreur:
            print(erreur)
            return 1
        print("Données de démonstration créées (toutes fictives) :")
        print(f"  - {len(resultat['gestionnaires'])} gestionnaires, {len(resultat['etudiants'])} étudiants, {resultat['documents']} documents,")
        print(f"    {resultat['telechargements']} téléchargements et {resultat['recherches']} recherches sur les {JOURS_HISTORIQUE} derniers jours.")
        print("\nComptes à utiliser (onglet « Gestionnaire / Admin ») :")
        for g in resultat["gestionnaires"]:
            print(f"  {g['email']}   mot de passe : {MOT_DE_PASSE_DEMO}")
        e = resultat["etudiants"][0]
        print("\nExemple d'étudiant (onglet « Étudiant ») :")
        print(f"  prénom : {e['prenom']}   nom : {e['nom']}   email : {e['email']}   code : {e['code']}")
        print("\nPour tout supprimer plus tard : python scripts/donnees_demo.py supprimer")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
