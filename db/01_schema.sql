-- Mémoria - création de la base centre_doc (MySQL 8)
-- À importer avec phpMyAdmin (onglet "Importer") ou en ligne de commande : mysql -u root < 01_schema.sql

CREATE DATABASE IF NOT EXISTS centre_doc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE centre_doc;

CREATE TABLE ufr (
    id_ufr INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(150) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE utilisateurs (
    id_utilisateur INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(80) NOT NULL,
    prenom VARCHAR(80) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL,
    id_ufr INT NULL,                                -- gestionnaires
    code_etudiant VARCHAR(30) NULL UNIQUE,          -- étudiants
    mot_de_passe_hash VARCHAR(255) NULL,            -- admin / gestionnaires (les étudiants n'ont pas de mot de passe)
    cree_le DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_utilisateur_ufr FOREIGN KEY (id_ufr) REFERENCES ufr(id_ufr),
    CONSTRAINT ck_email_ugb CHECK (email LIKE '%@ugb.edu.sn'),
    CONSTRAINT ck_role CHECK (role IN ('ADMIN', 'GESTIONNAIRE', 'ETUDIANT')),
    CONSTRAINT ck_gestionnaire_ufr CHECK (role <> 'GESTIONNAIRE' OR id_ufr IS NOT NULL),
    CONSTRAINT ck_etudiant_code CHECK (role <> 'ETUDIANT' OR code_etudiant IS NOT NULL)
) ENGINE=InnoDB;

CREATE TABLE documents (
    id_document INT AUTO_INCREMENT PRIMARY KEY,
    titre VARCHAR(255) NOT NULL,
    auteur VARCHAR(150) NOT NULL,
    encadrant VARCHAR(150) NULL,
    annee INT NOT NULL,
    type VARCHAR(10) NOT NULL,
    id_ufr INT NOT NULL,
    discipline VARCHAR(100) NULL,
    resume TEXT NULL,
    mots_cles TEXT NULL,
    chemin_pdf VARCHAR(255) NULL,
    niveau_acces VARCHAR(25) NOT NULL,
    resume_genere_ia TINYINT(1) NOT NULL DEFAULT 0,
    cree_par INT NULL,
    cree_le DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_document_ufr FOREIGN KEY (id_ufr) REFERENCES ufr(id_ufr),
    CONSTRAINT fk_document_createur FOREIGN KEY (cree_par) REFERENCES utilisateurs(id_utilisateur)
        ON DELETE SET NULL,
    CONSTRAINT ck_type CHECK (type IN ('THESE', 'MEMOIRE')),
    CONSTRAINT ck_niveau_acces CHECK (niveau_acces IN ('TELECHARGEABLE', 'CONSULTATION_SEULE', 'RESTREINT'))
) ENGINE=InnoDB;

CREATE TABLE telechargements (
    id_telechargement INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur INT NOT NULL,
    id_document INT NOT NULL,
    date_telechargement DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_telechargement_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_telechargement_document FOREIGN KEY (id_document)
        REFERENCES documents(id_document) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Partie IA / data (utilisée aux étapes 5 et 6) : l'embedding est stocké en binaire (float32)
CREATE TABLE document_chunks (
    id_chunk INT AUTO_INCREMENT PRIMARY KEY,
    id_document INT NOT NULL,
    position INT NOT NULL,
    contenu TEXT NOT NULL,
    embedding LONGBLOB NULL,
    CONSTRAINT fk_chunk_document FOREIGN KEY (id_document)
        REFERENCES documents(id_document) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE recherches (
    id_recherche INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur INT NULL,
    requete TEXT NOT NULL,
    nb_resultats INT NULL,
    date_recherche DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_recherche_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs(id_utilisateur) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_documents_ufr ON documents(id_ufr);
CREATE INDEX idx_documents_annee ON documents(annee);
CREATE INDEX idx_telechargements_document ON telechargements(id_document);
CREATE INDEX idx_telechargements_utilisateur ON telechargements(id_utilisateur);
CREATE INDEX idx_chunks_document ON document_chunks(id_document);
