"""Exceptions métier personnalisées : toute règle violée lève l'une d'elles."""


class ErreurMetier(Exception):
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthentificationError(ErreurMetier):
    status_code = 401


class AccesRefuseError(ErreurMetier):
    status_code = 403


class UtilisateurIntrouvableError(ErreurMetier):
    status_code = 404


class UfrIntrouvableError(ErreurMetier):
    status_code = 404


class DocumentIntrouvableError(ErreurMetier):
    status_code = 404


class DoublonError(ErreurMetier):
    status_code = 409


class RegleMetierError(ErreurMetier):
    status_code = 409


class ChampInvalideError(ErreurMetier):
    status_code = 422
