-- Données de démonstration (fictives). Le compte ADMIN est créé par l'API au démarrage.
-- À importer APRÈS 01_schema.sql.
USE centre_doc;

INSERT IGNORE INTO ufr (nom) VALUES
    ('UFR Sciences Appliquées et Technologie'),
    ('UFR Lettres et Sciences Humaines'),
    ('UFR Sciences Juridiques et Politiques'),
    ('UFR Sciences Economiques et de Gestion'),
    ('UFR Sciences de la Santé'),
    ('UFR Civilisations, Religions, Arts et Communication'),
    ('UFR Sciences Agronomiques, d''Aquaculture et des Technologies Alimentaires');

INSERT IGNORE INTO utilisateurs (nom, prenom, email, role, code_etudiant) VALUES
    ('Diop', 'Awa', 'awa.diop@ugb.edu.sn', 'ETUDIANT', 'DEMO0001');
