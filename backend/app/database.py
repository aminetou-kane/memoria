import ssl

import pymysql
from pymysql.cursors import DictCursor

from .config import settings

ERREUR_DOUBLON = 1062  # code MySQL "Duplicate entry"


class Connexion:
    """Petite enveloppe autour de PyMySQL : execute() renvoie directement un curseur."""

    def __init__(self, avec_base: bool = True):
        self._conn = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name if avec_base else None,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            ssl=ssl.create_default_context() if settings.db_ssl else None,
        )

    def execute(self, sql, params=None):
        curseur = self._conn.cursor()
        curseur.execute(sql, params)
        return curseur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def ouvrir_connexion(avec_base: bool = True) -> Connexion:
    return Connexion(avec_base)


def est_doublon(erreur: Exception) -> bool:
    return bool(erreur.args) and erreur.args[0] == ERREUR_DOUBLON


def get_conn():
    """Une connexion par requête. Sans commit explicite, tout est annulé à la fermeture."""
    conn = ouvrir_connexion()
    try:
        yield conn
    finally:
        conn.close()
