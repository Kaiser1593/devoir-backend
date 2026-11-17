# Bibliothèque — Projet final E4 Full Stack Backend

Application web Django de **gestion de bibliothèque** (thème A) : livres, auteurs, adhérents et emprunts,
avec interface web, API REST (Django REST Framework), import/export JSON et XML.

**Technologies** : Python 3.12+, Django, Django REST Framework, SQLite, HTML/CSS, JavaScript (`fetch`).

## Fonctionnalités

- **Livres** : catalogue paginé, recherche (titre, auteur, ISBN), filtre « disponibles », tri, détail avec historique, création / modification / suppression.
- **Auteurs** et **adhérents** : CRUD complet (la suppression d'un élément encore référencé est refusée avec un message clair).
- **Emprunts** : création, liste filtrable (en cours / en retard / rendus), retour d'un livre.
- **Tableau de bord** : compteurs et liste des retards.
- **JavaScript** : recherche en direct via `fetch()` vers l'API, retour d'un emprunt sans rechargement de page, affichage/masquage du résumé d'un livre.
- **API REST** : listes, détails, création, modification, suppression, action « retour ».
- **JSON / XML** : lecture et analyse de fichiers locaux en objets Python (dataclasses), import en base (page web ou commande), export du catalogue en JSON ou XML.

### Règles métier (vérifiées côté serveur, dans `Emprunt.clean()` / `Livre.clean()`)

1. Un emprunt est **refusé si le livre est indisponible** (tous les exemplaires sont empruntés).
2. Un adhérent ne peut pas avoir plus de **3 emprunts simultanés**.
3. Les dates doivent être cohérentes (retour prévu / réel ≥ date d'emprunt).
4. On ne peut pas réduire le nombre d'exemplaires d'un livre en dessous du nombre d'exemplaires actuellement prêtés.

Ces règles s'appliquent partout : formulaires, API, admin, shell (`Emprunt.save()` appelle `full_clean()`).

## Installation et lancement

```bash
# 1. (Recommandé) créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Créer la base SQLite
python manage.py migrate

# 4. Charger les données fictives (data/livres.json, data/livres.xml, data/adherents.json + emprunts)
python manage.py charger_donnees

# 5. (Optionnel) créer un super-utilisateur pour /admin/
python manage.py createsuperuser

# 6. Lancer le serveur
python manage.py runserver
```

Application : <http://127.0.0.1:8000/> — API : <http://127.0.0.1:8000/api/> — Admin : <http://127.0.0.1:8000/admin/>

## Tests

```bash
python manage.py test
```

28 tests automatisés (règles métier, vues et formulaires, API et codes HTTP, analyse / import / export JSON et XML, cas invalides).

## Routes principales (interface web)

| Route | Description |
|---|---|
| `/` | Tableau de bord |
| `/livres/` · `/livres/nouveau/` · `/livres/<id>/` · `/livres/<id>/modifier/` · `/livres/<id>/supprimer/` | CRUD livres (`?q=`, `?dispo=1`, `?tri=titre\|auteur\|annee`) |
| `/auteurs/` (+ `nouveau/`, `<id>/modifier/`, `<id>/supprimer/`) | CRUD auteurs |
| `/adherents/` (+ `nouveau/`, `<id>/`, `<id>/modifier/`, `<id>/supprimer/`) | CRUD adhérents |
| `/emprunts/` · `/emprunts/nouveau/` · `/emprunts/<id>/retour/` (POST) | Emprunts (`?statut=en_cours\|retards\|rendus`) |
| `/import/` | Import d'un fichier `.json` ou `.xml` |
| `/export/livres.json` · `/export/livres.xml` | Export du catalogue |

## Endpoints API

| Méthode | Endpoint | Description | Codes |
|---|---|---|---|
| GET / POST | `/api/livres/` | Liste (`?search=`, `?disponible=1`, `?page=`) / création | 200 / 201, 400 |
| GET / PUT / PATCH / DELETE | `/api/livres/<id>/` | Détail / modification / suppression | 200, 204, 400, 404, 409 |
| GET / POST | `/api/auteurs/` · `/api/auteurs/<id>/` | Auteurs (CRUD) | idem |
| GET / POST | `/api/adherents/` · `/api/adherents/<id>/` | Adhérents (CRUD) | idem |
| GET / POST | `/api/emprunts/` | Liste (`?statut=en_cours\|en_retard\|rendus`) / création d'un emprunt | 200 / 201, 400 (règle métier) |
| GET | `/api/emprunts/<id>/` | Détail d'un emprunt | 200, 404 |
| POST | `/api/emprunts/<id>/retour/` | Enregistre le retour | 200, 404, 409 (déjà rendu) |

Exemples :

```bash
curl "http://127.0.0.1:8000/api/livres/?search=verne&disponible=1"
curl -X POST http://127.0.0.1:8000/api/emprunts/ -H "Content-Type: application/json" -d "{\"livre\": 1, \"adherent\": 2}"
```

## Format des fichiers JSON / XML

Voir `data/livres.json` et `data/livres.xml`. Un livre est identifié par son ISBN (10 ou 13 chiffres) : s'il existe déjà, il est mis à jour, sinon créé.
Les lignes invalides sont signalées dans un rapport sans bloquer les autres. Le code se trouve dans `catalogue/services/echanges.py`.

## Structure du projet

```
bibliotheque/            configuration Django (settings, urls)
catalogue/
  models.py              Auteur, Livre, Adherent, Emprunt + règles métier
  forms.py, views.py     formulaires (validation serveur) et vues, urls.py
  serializers.py, api_views.py, api_urls.py   API REST
  services/echanges.py   lecture / import / export JSON et XML
  management/commands/charger_donnees.py      données fictives
  templates/, static/    templates (héritage de base.html), CSS, JavaScript
  tests.py               tests automatisés
data/                    fichiers JSON / XML fictifs
```

## Limites connues

- Pas d'authentification : l'interface et l'API sont ouvertes (projet pédagogique, usage local uniquement).
- Contrôle de disponibilité sans verrou de base de données : deux emprunts exactement simultanés du dernier exemplaire pourraient théoriquement passer.
- Le tri n'est pas pris en compte par la recherche en direct (JavaScript) : seul le tri serveur existe.
- La clé secrète et `DEBUG=1` sont ceux du développement ; ne pas déployer en l'état.
- L'analyse XML utilise `xml.etree` de la bibliothèque standard : à n'utiliser que sur des fichiers de confiance.
