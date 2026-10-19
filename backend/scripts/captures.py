"""Prend AUTOMATIQUEMENT les captures d'écran de l'application (README, GitHub, LinkedIn).

Avant de lancer :
  1. l'application tourne (uvicorn app.main:app --reload) et WAMP est vert ;
  2. les données de démonstration sont chargées (python scripts\\donnees_demo.py charger) ;
  3. Microsoft Edge ou Google Chrome est installé (Edge l'est déjà sous Windows) ;
  4. une seule installation, une fois :  pip install playwright   (aucun navigateur n'est téléchargé : Edge est utilisé).

Lancer (depuis le dossier backend, environnement virtuel activé) :

    python scripts\\captures.py

Les images sont enregistrées dans le dossier docs\\captures du projet. Option : --sortie "C:\\mon\\dossier"
"""
import os
import sys
import urllib.request
from pathlib import Path

DOSSIER_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOSSIER_BACKEND))

from app.config import settings  # noqa: E402  (lit aussi backend/.env : mot de passe de l'administrateur)

URL = os.getenv("APP_URL", "http://127.0.0.1:8000").rstrip("/")
LARGEUR, HAUTEUR, ECHELLE = 1440, 900, 1.5       # 2160 x 1350 pixels : net même sur un grand écran

ETUDIANT = {"prenom": "Mariama", "nom": "Fall", "email": "demo.mariama.fall@ugb.edu.sn", "code_etudiant": "DMO2026001"}
GESTIONNAIRE = {"email": "demo.gestionnaire.agro@ugb.edu.sn", "mot_de_passe": "Demo2026!"}


class ErreurCapture(Exception):
    """Erreur expliquée en français à l'utilisateur."""


def lancer_navigateur(playwright):
    """Utilise Edge (ou Chrome) déjà installé : rien à télécharger."""
    args = os.getenv("NAVIGATEUR_ARGS", "").split()
    chemin = os.getenv("NAVIGATEUR_CHEMIN")          # pour utiliser un autre navigateur
    if chemin:
        return playwright.chromium.launch(executable_path=chemin, args=args)
    for canal in ("msedge", "chrome"):
        try:
            return playwright.chromium.launch(channel=canal, args=args)
        except Exception:
            continue
    raise ErreurCapture("Ni Microsoft Edge ni Google Chrome n'a été trouvé. Installe l'un des deux, puis relance.")


def verifier_application():
    try:
        with urllib.request.urlopen(URL + "/sante", timeout=5) as reponse:
            if reponse.status != 200:
                raise OSError(reponse.status)
    except Exception:
        raise ErreurCapture(f"L'application ne répond pas sur {URL}. Lance-la d'abord (uvicorn app.main:app --reload).")


def se_connecter(page, onglet, champs, role_attendu):
    page.goto(URL + "/app/")
    page.wait_for_selector(".boite-connexion")
    if onglet == "personnel":
        page.click(".onglets button:nth-child(2)")
    for nom, valeur in champs.items():
        page.fill(f".boite-connexion [name={nom}]", valeur)
    page.click(".boite-connexion button[type=submit]")
    try:
        page.wait_for_selector(".entete", timeout=10000)
    except Exception:
        erreur = page.locator(".boite-connexion .erreur-formulaire:not([hidden])")
        detail = erreur.first.text_content() if erreur.count() else "pas de réponse"
        if role_attendu == "ADMIN":
            raise ErreurCapture(f"Connexion administrateur impossible ({detail}). Vérifie ADMIN_EMAIL et ADMIN_PASSWORD dans backend\\.env.")
        raise ErreurCapture(f"Connexion de démonstration impossible ({detail}). As-tu chargé les données de démonstration ? "
                            "(python scripts\\donnees_demo.py charger)")


def defiler_vers(page, titre):
    """Fait défiler la page pour que la carte portant ce titre apparaisse juste sous l'en-tête."""
    page.evaluate("""(titre) => {
        const h = [...document.querySelectorAll('h3')].find((x) => x.textContent.startsWith(titre));
        window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 90);
    }""", titre)
    page.wait_for_timeout(300)


def principal(arguments) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    sortie = DOSSIER_BACKEND.parent / "docs" / "captures"
    if "--sortie" in arguments:
        sortie = Path(arguments[arguments.index("--sortie") + 1])
    sortie.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Il manque une installation (une seule fois) :  pip install playwright")
        return 1

    faites = []

    def prendre(cible, nom, **options):
        """Capture une page entière visible, ou un seul élément (cible = page ou élément)."""
        getattr(cible, "page", cible).wait_for_timeout(350)     # un élément connaît sa page ; une page est elle-même
        cible.screenshot(path=str(sortie / nom), **options)
        faites.append(nom)
        print("  OK  ", nom)

    try:
        verifier_application()
        with sync_playwright() as p:
            navigateur = lancer_navigateur(p)

            def nouvelle_page(**options):
                contexte = navigateur.new_context(viewport={"width": LARGEUR, "height": HAUTEUR}, device_scale_factor=ECHELLE,
                                                  locale="fr-FR", **options)
                return contexte.new_page()

            print("Captures en cours (environ 1 minute)...")

            # 1) page de connexion
            page = nouvelle_page()
            page.goto(URL + "/app/")
            page.wait_for_selector(".boite-connexion")
            page.wait_for_load_state("networkidle")
            prendre(page, "01-connexion.jpg", type="jpeg", quality=88)       # une photo : le JPEG est bien plus léger

            # 2-3) espace étudiant : recherche, puis fiche d'un document
            se_connecter(page, "etudiant", ETUDIANT, "ETUDIANT")
            page.wait_for_selector(".resultat")
            page.fill("input[name=q]", "santé")
            page.press("input[name=q]", "Enter")
            page.wait_for_function("document.querySelector('.resume-compteur') && /trouvé/.test(document.querySelector('.resume-compteur').textContent)")
            page.evaluate("document.activeElement.blur()")
            prendre(page, "02-etudiant-recherche.png")
            page.click(".resultat h3 button")
            page.wait_for_selector(".modal")
            prendre(page, "03-etudiant-fiche-document.png")
            page.keyboard.press("Escape")

            # 4-5) espace gestionnaire : liste des documents, puis formulaire d'ajout (rempli, mais non envoyé)
            page = nouvelle_page()
            se_connecter(page, "personnel", GESTIONNAIRE, "GESTIONNAIRE")
            page.wait_for_selector(".contenu tbody tr")
            prendre(page, "04-gestionnaire-documents.png")
            page.click("text=+ Ajouter un document")
            page.wait_for_selector(".modal")
            page.fill(".modal [name=titre]", "Impact de l'irrigation sur la production maraîchère")
            page.fill(".modal [name=auteur]", "Awa Diop")
            page.fill(".modal [name=encadrant]", "Pr Alioune Diouf")
            page.fill(".modal [name=discipline]", "Agronomie")
            page.fill(".modal [name=resume]", "Cette étude compare plusieurs techniques d'irrigation et mesure leur effet sur le rendement.")
            page.fill(".modal [name=mots_cles]", "irrigation, maraîchage, rendement")
            page.select_option(".modal [name=niveau_acces]", "CONSULTATION_SEULE")
            page.evaluate("document.activeElement.blur()")
            prendre(page, "05-gestionnaire-ajout-document.png")
            page.keyboard.press("Escape")

            # 6-8) espace administrateur : tableau de bord (haut, puis bas), utilisateurs
            page = nouvelle_page()
            se_connecter(page, "personnel", {"email": settings.admin_email, "mot_de_passe": settings.admin_password}, "ADMIN")
            page.wait_for_function("document.querySelectorAll('.kpi').length >= 4 && document.querySelectorAll('canvas').length >= 4")
            page.wait_for_timeout(1800)                      # laisse finir l'animation des graphiques
            prendre(page, "06-admin-tableau-de-bord.png")
            defiler_vers(page, "Répartition par discipline")
            page.wait_for_timeout(1200)
            prendre(page, "07-admin-graphiques.png")
            carte = page.locator(".carte", has=page.locator("h3", has_text="Recherches sans résultat")).last
            carte.scroll_into_view_if_needed()
            prendre(carte, "08-admin-recherches-sans-resultat.png")      # la carte seule, bien cadrée
            page.click('.menu a[data-vue="utilisateurs"]')
            page.wait_for_selector(".contenu tbody tr")
            page.evaluate("window.scrollTo(0, 0)")
            prendre(page, "09-admin-utilisateurs.png")

            # 10) version téléphone (la recherche de l'étudiant)
            mobile = navigateur.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                                            has_touch=True, locale="fr-FR").new_page()
            se_connecter(mobile, "etudiant", ETUDIANT, "ETUDIANT")
            mobile.wait_for_selector(".resultat")
            mobile.fill("input[name=q]", "santé")
            mobile.press("input[name=q]", "Enter")
            mobile.wait_for_function("document.querySelector('.resume-compteur') && /trouvé/.test(document.querySelector('.resume-compteur').textContent)")
            mobile.evaluate("document.activeElement.blur()")
            prendre(mobile, "10-mobile-recherche.png")

            # 11) documentation de l'API (la page vient d'Internet : on l'ignore si elle ne s'affiche pas)
            page = nouvelle_page()
            page.goto(URL + "/docs")
            try:
                page.wait_for_selector(".swagger-ui .opblock", timeout=12000)
                prendre(page, "11-api-documentation.png")
            except Exception:
                print("  --   11-api-documentation.png ignorée (la page /docs a besoin d'Internet)")
            navigateur.close()
    except ErreurCapture as erreur:
        print("\nImpossible de continuer :", erreur)
        return 1

    print(f"\nTerminé : {len(faites)} captures dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
