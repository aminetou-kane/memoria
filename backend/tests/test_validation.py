import pytest

from app.exceptions import ChampInvalideError
from app.security import create_token, decode_token, hash_password, verify_password
from app.validation import exiger_texte, valider_email_ugb, valider_mot_de_passe


def test_email_ugb_valide():
    assert valider_email_ugb("  Kane.Aminetou@UGB.edu.sn ") == "kane.aminetou@ugb.edu.sn"


@pytest.mark.parametrize("email", ["a@gmail.com", "a@ugb.edu.sn.fr", "ugb.edu.sn", "", None])
def test_email_ugb_invalide(email):
    with pytest.raises(ChampInvalideError):
        valider_email_ugb(email)


def test_champ_obligatoire():
    with pytest.raises(ChampInvalideError):
        exiger_texte("   ", "nom")


def test_mot_de_passe_trop_court():
    with pytest.raises(ChampInvalideError):
        valider_mot_de_passe("abc")


def test_hash_et_verification():
    h = hash_password("Secret123!")
    assert verify_password("Secret123!", h)
    assert not verify_password("autre", h)


def test_token_aller_retour():
    payload = decode_token(create_token(7, "ADMIN"))
    assert payload["sub"] == "7" and payload["role"] == "ADMIN"
