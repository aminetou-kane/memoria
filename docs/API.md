# Documentation de l'API

Une documentation interactive (Swagger) est générée automatiquement par l'application : http://127.0.0.1:8000/docs

L'authentification utilise un jeton JWT envoyé dans l'en-tête `Authorization: Bearer <jeton>`. Les erreurs métier renvoient un JSON de la forme `{"erreur": "DoublonError", "message": "..."}`.

## Authentification

| Méthode | Route | Accès |
|---|---|---|
| POST | `/auth/login` | administrateur, gestionnaire (email et mot de passe) |
| POST | `/auth/login-etudiant` | étudiant (prénom, nom, email UGB, code étudiant) |
| GET | `/auth/me` | utilisateur connecté |

## Utilisateurs et UFR

| Méthode | Route | Accès |
|---|---|---|
| GET | `/users?q=&role=` | administrateur |
| POST | `/users/gestionnaires`, `/users/etudiants` | administrateur |
| PUT / DELETE | `/users/{id}` (PUT avec `id_ufr` : affectation à une UFR) | administrateur |
| GET | `/ufr` | utilisateur connecté |
| POST / PUT / DELETE | `/ufr`, `/ufr/{id}` | administrateur |

## Documents

| Méthode | Route | Accès |
|---|---|---|
| POST | `/documents` (formulaire et PDF) | gestionnaire |
| GET | `/documents/gestion?q=` | gestionnaire (son UFR) |
| PUT / DELETE | `/documents/{id}` | gestionnaire (son UFR) |
| GET | `/documents/{id}/disponibilite` | gestionnaire (son UFR) |
| GET | `/documents/{id}` (fiche détaillée) | étudiant ; gestionnaire (son UFR) |
| GET | `/documents/{id}/download` | étudiant, si `TELECHARGEABLE` |
| GET | `/documents/recherche` | étudiant |
| GET | `/telechargements/moi` | étudiant |
| GET | `/telechargements/gestion`, `/telechargements/document/{id}` | gestionnaire (son UFR) |

### Règles métier

- `TELECHARGEABLE` : fiche et PDF ; `CONSULTATION_SEULE` : métadonnées et résumé seulement ; `RESTREINT` : ni consultable ni téléchargeable par l'étudiant.
- Un gestionnaire ne gère que les documents de son UFR.
- Un document `TELECHARGEABLE` doit avoir un PDF.
- Deux documents ne peuvent pas avoir le même titre, le même auteur et la même année.
- L'email d'un utilisateur doit être un email UGB (`@ugb.edu.sn`) ; email et code étudiant sont uniques.
- Chaque téléchargement est enregistré dans l'historique.

### Recherche (`GET /documents/recherche`)

Tous les critères sont facultatifs et se combinent.

| Paramètre | Rôle |
|---|---|
| `q` | texte libre : chaque mot est cherché dans le titre, l'auteur, l'encadrant, la discipline, les mots-clés et le résumé |
| `titre`, `auteur`, `discipline` | le champ contient ce texte |
| `mot_cle` | mot-clé exact (mot entier : « ia » ne trouve pas « financial ») |
| `annee`, `id_ufr` | année / numéro d'UFR |
| `type` | `THESE` ou `MEMOIRE` |
| `telechargeable` | `true` : uniquement les documents dont le PDF est téléchargeable |
| `page`, `taille` | pagination (10 résultats par défaut, 50 au maximum) |

La recherche ignore les majuscules et les accents. Les documents `RESTREINT` n'apparaissent jamais dans les résultats d'un étudiant. Chaque recherche est enregistrée (table `recherches`, sans identité dans les statistiques) pour repérer les besoins non couverts.

## Statistiques et exports

Réservés à l'administrateur (vue globale, filtrable par UFR avec `?id_ufr=`) et au gestionnaire (uniquement son UFR).

| Route | Contenu |
|---|---|
| `/statistiques/globales` | documents (par niveau d'accès), téléchargements (total, 30 derniers jours, étudiants distincts) ; pour l'administrateur : utilisateurs par rôle, recherches |
| `/statistiques/top-documents?limite=10` | documents les plus téléchargés |
| `/statistiques/activite-ufr` | documents et téléchargements par UFR |
| `/statistiques/repartition/{axe}` | répartition par `discipline`, `annee`, `type` ou `niveau_acces` |
| `/statistiques/documents-restreints` | documents sous embargo |
| `/statistiques/recherches-sans-resultat` | recherches sans résultat (administrateur) |
| `/statistiques/export/{jeu}` | export CSV : `top-documents`, `activite-ufr`, `repartition-discipline`, `repartition-annee`, `documents-restreints`, `recherches-sans-resultat` |

Les fichiers CSV utilisent le séparateur `;` et l'encodage UTF-8 avec BOM : ils s'ouvrent directement dans Excel en français.
