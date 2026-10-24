from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .demo import comptes_demo, completer_demo, preparer_demo
from .database import ouvrir_connexion
from .exceptions import ErreurMetier
from .routers import auth, documents, recherche, statistiques, telechargements, ufr, users
from .security import hash_password


def initialiser_admin() -> None:
    """Crée le compte administrateur initial s'il n'existe pas."""
    conn = ouvrir_connexion()
    try:
        existe = conn.execute(
            "SELECT 1 FROM utilisateurs WHERE email = %s", (settings.admin_email,)
        ).fetchone()
        if not existe:
            conn.execute(
                "INSERT INTO utilisateurs (nom, prenom, email, role, mot_de_passe_hash) "
                "VALUES ('Système', 'Administrateur', %s, 'ADMIN', %s)",
                (settings.admin_email, hash_password(settings.admin_password)),
            )
            conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.demo_mode:
        preparer_demo()          # crée les tables si la base est vide
    initialiser_admin()
    if settings.demo_mode:
        completer_demo()         # données fictives + PDF
    yield


app = FastAPI(
    title=settings.app_nom,
    description="Système d'information des centres de documentation de l'UGB (thèses et mémoires).",
    version="0.6.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErreurMetier)
async def erreur_metier_handler(request: Request, exc: ErreurMetier):
    return JSONResponse(
        status_code=exc.status_code,
        content={"erreur": type(exc).__name__, "message": exc.message},
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(ufr.router)
app.include_router(recherche.router)  # avant documents : /documents/recherche ne doit pas être pris pour un id
app.include_router(documents.router)
app.include_router(telechargements.router)
app.include_router(statistiques.router)


@app.get("/sante", tags=["Santé"])
def sante():
    reponse = {"application": settings.app_nom, "sous_titre": settings.app_sous_titre, "statut": "ok"}
    if settings.demo_mode:
        reponse["comptes_demo"] = comptes_demo()
    return reponse


@app.get("/", include_in_schema=False)
def racine():
    return RedirectResponse("/app/")


class InterfaceStatique(StaticFiles):
    """Sert l'interface en demandant au navigateur de revérifier les fichiers à chaque fois
    (évite de voir une ancienne version après une mise à jour)."""

    async def get_response(self, path, scope):
        reponse = await super().get_response(path, scope)
        reponse.headers["Cache-Control"] = "no-cache"
        return reponse


# Interface web (HTML/CSS/JavaScript, sans outil de compilation) : http://127.0.0.1:8000/app/
app.mount("/app", InterfaceStatique(directory=Path(__file__).resolve().parent / "static", html=True), name="interface")
