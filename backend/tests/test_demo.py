"""Mode démonstration : comptes de test et découpage des scripts SQL (sans base de données)."""
from app import demo
from app.config import settings


def test_comptes_demo_absents_hors_mode_demo(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    assert demo.comptes_demo() == []


def test_comptes_demo_couvrent_les_trois_roles(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    comptes = demo.comptes_demo()
    assert [c["role"] for c in comptes] == ["ETUDIANT", "GESTIONNAIRE", "ADMIN"]
    assert comptes[0]["code_etudiant"] and comptes[1]["mot_de_passe"] and comptes[2]["email"] == settings.admin_email


def test_scripts_sql_decoupes_sans_create_database():
    for nom in ("01_schema.sql", "02_seed.sql"):
        instructions = demo._instructions_sql(demo.DOSSIER_SQL / nom)
        assert instructions
        assert not any(i.upper().startswith(("CREATE DATABASE", "USE")) for i in instructions)
    assert len(demo._instructions_sql(demo.DOSSIER_SQL / "01_schema.sql")) == 11
