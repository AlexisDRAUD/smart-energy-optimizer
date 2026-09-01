# EnerVision — Smart Energy Optimizer (Backend API)

> Ce README est destiné à la fois aux développeurs humains et aux agents IA
> (Claude Code, Copilot, etc.) intervenant sur ce projet. Il contient tout le
> contexte métier et technique nécessaire pour travailler efficacement sans
> avoir à redemander les infos de base.

## 1. Contexte du projet

**EnerVision** est une startup fictive spécialisée dans l'optimisation
énergétique par l'IA. Ce dépôt contient le **backend de l'API sécurisée**
qui alimente un dashboard web de suivi de consommation énergétique
industrielle.

Le projet est réalisé dans le cadre d'une piscine pédagogique (EADL) de
2 semaines, en équipe de ~5 personnes avec des rôles répartis (Product Owner,
Tech Lead, Cloud/DevOps, Data & IA, Fullstack Dev).

**Objectif produit :** livrer une plateforme capable de :
- Collecter et stocker des données de consommation énergétique (via un pipeline ETL)
- Anticiper les pics de consommation via un modèle prédictif (ML)
- Recommander des actions correctives
- Exposer tout ça via une **API sécurisée** consommée par un dashboard front-end

**Critère d'évaluation ultime du projet (à garder en tête pour toute décision technique) :**
> "Pourrait-on réellement déployer cette solution auprès d'un client pilote demain ?"

## 2. Ce dépôt = le backend uniquement

Ce dépôt couvre **uniquement l'API back-end** en FastAPI. Le front-end
(dashboard) est un projet séparé qui consomme cette API.

## 3. Stack technique

| Composant | Techno |
|---|---|
| Framework API | FastAPI |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | JWT (OAuth2PasswordBearer) + rôles multiples par utilisateur |
| Base de données | PostgreSQL (à confirmer selon choix infra, voir §6) |
| Tests | Pytest |
| Conteneurisation | Docker / Docker Compose |
| Données de démonstration | Jeu de données local SQLAlchemy, initialisé dans PostgreSQL |

## 4. Architecture du dépôt

```
app/
├── main.py              # Entrée FastAPI, montage des routers
├── config.py            # Settings (variables d'env via pydantic-settings)
├── api/v1/endpoints/    # Routes HTTP (auth, users, sites, readings, alerts, predictions, stats)
├── core/                # Sécurité (JWT, hash), exceptions, logging
├── models/              # Modèles SQLAlchemy (User, Role, Site, Reading, Alert)
├── schemas/             # Schémas Pydantic (validation entrée/sortie API)
├── crud/                # Requêtes base de données
├── services/            # Logique métier (ETL local, prédiction, alertes)
├── db/                  # Session DB, base declarative, seed initial
└── etl/                 # Pipeline ETL (extract / transform / load), exécutable indépendamment
```

**Principe de couches à respecter :**
`api/` (HTTP) → `services/` ou `crud/` (logique/données) → `models/` (DB).
Ne jamais mettre de logique métier directement dans les fichiers `api/`.

## 5. Données de démonstration locales

Le projet ne dépend d'**aucune API Mock IoT**. Toutes les données sont
persistées dans PostgreSQL et un jeu de démonstration cohérent est créé lors du
premier démarrage de l'API (`app/db/init_db.py`). Cette approche rend le projet
autonome et reproductible en local comme en conteneur.

Le seed contient :

| Donnée | Contenu |
|---|---|
| Sites | Trois sites industriels fictifs à Lyon, Grenoble et Nantes |
| Relevés | 48 heures de consommation par site, avec variations jour/nuit |
| Qualité | Trois relevés dégradés dont la valeur brute reste `NULL` |
| Alertes | Une alerte active sur le site à forte consommation |
| Utilisateurs | Quatre utilisateurs fictifs couvrant les rôles admin, operator, data_analyst et user |

Les identifiants de démonstration sont `camille.admin` (admin),
`lucas.operator` (operator), `ines.analyst` (data analyst) et `marc.viewer`
(lecture). Le mot de passe est défini par `SEED_USER_PASSWORD` et vaut
`EnerVisionDemo2026!` uniquement en développement.

**Endpoints principaux :**

| Endpoint | Rôle |
|---|---|
| `POST /api/v1/auth/token` | Obtenir un JWT avec un utilisateur de la base |
| `GET /api/v1/sites` | Lister les sites industriels |
| `GET /api/v1/sites/{site_id}/current` | Lire le dernier relevé stocké |
| `GET /api/v1/readings` / `POST /api/v1/readings/sites/{site_id}` | Consulter ou ajouter des relevés persistés |
| `GET /api/v1/alerts` | Lister les alertes de consommation |
| `GET /api/v1/predictions/sites/{site_id}/next` | Calculer une prévision depuis l'historique local |
| `GET /api/v1/stats/summary` | Résumer le parc stocké en base |

**⚠️ Point critique — gestion des NULL :**
Les relevés peuvent contenir une valeur brute `null` (maintenance capteur,
perte réseau) avec `data_quality` (`good` / `partial` / `degraded` /
`critical`) et `null_reasons`. **Ne jamais filtrer/ignorer un `null` : il doit
être stocké tel quel avec son flag qualité.** Le pipeline ETL applique
explicitement un forward fill à la valeur imputée, sans modifier la valeur
brute (voir `app/etl/transform.py`).

**Bonne pratique imposée :** toujours stocker la valeur brute (NULL compris)
**et** la valeur imputée dans deux colonnes distinctes. Ne jamais écraser un
NULL sans traçabilité.

## 6. Contraintes d'architecture (à respecter impérativement)

- **Interdiction d'utiliser des solutions no-code ou du Backend-as-a-Service
  sans justification d'architecture écrite** dans le dossier de conception.
  Toute techno "clé en main" doit être argumentée.
- **Infra cible :** AWS/Azure (accès école) ou serveur on-premise via SSH
  (Docker/Docker Compose pré-installés). Le choix est documenté séparément
  dans le dossier de conception (EC01) — ne pas présumer de l'infra dans le
  code, tout doit rester conteneurisé et portable.
- **Sécurité by design attendue :** authentification JWT, gestion des
  secrets hors code (variables d'env, jamais commit), surface d'attaque
  réduite, scans de sécurité (OWASP ZAP, Trivy) prévus en CI/CD.
- **Tests automatisés obligatoires**, fonctionnels et non-fonctionnels,
  intégrés au pipeline CI/CD.

## 7. Authentification & rôles

- Auth par **JWT** (`OAuth2PasswordBearer`), login via `POST /api/v1/auth/token`.
- Un utilisateur peut avoir **plusieurs rôles** (relation many-to-many
  `User` ↔ `Role`), stockés en base et inclus dans le payload du token.
- Les rôles envisagés : `admin`, `user`, `moderator`/`operator`, `editor`
  (à ajuster selon les besoins métier réels : ex. `site_manager`,
  `data_analyst`...).
- Vérification des rôles via une dépendance réutilisable (`RoleChecker`)
  dans `app/api/deps.py`, appliquée par route selon le besoin.

## 8. Démarrage du projet

### Démarrage local

Prérequis : Python 3.11 ou version ultérieure.

```bash
# Depuis la racine du dépôt : créer l'environnement Python (une seule fois)
python3 -m venv .venv

# Installer les dépendances (une seule fois)
.venv/bin/python -m pip install -r requirements.txt

# Optionnel : définir les variables locales
cp .env.example .env

# Appliquer les migrations et démarrer l'API
./scripts/start.sh
```

Le script applique les migrations Alembic puis démarre l'API avec rechargement
automatique sur `http://localhost:8000`. Au premier démarrage, les données de
démonstration sont insérées automatiquement dans la base.

Vérifier le démarrage :

```bash
curl http://localhost:8000/health
```

La documentation interactive est disponible sur `http://localhost:8000/docs`.

### Démarrage avec Docker Compose

```bash
# Créer la configuration locale et remplacer les valeurs de développement
cp .env.example .env

# Démarrer PostgreSQL et l'API
JWT_SECRET_KEY="une-cle-secrete-d-au-moins-32-caracteres" docker compose up --build
```

L'API est exposée sur `http://localhost:8000`. Pour l'arrêter, utilisez
`docker compose down`.

### Comptes de démonstration

Le mot de passe de développement est `EnerVisionDemo2026!` (ou la valeur de
`SEED_USER_PASSWORD` dans `.env`).

| Utilisateur | Rôle principal |
|---|---|
| `camille.admin` | admin |
| `lucas.operator` | operator |
| `ines.analyst` | data_analyst |
| `marc.viewer` | user |

```bash
# Obtenir un jeton JWT pour appeler les routes protégées
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=camille.admin&password=EnerVisionDemo2026!"
```

### Commandes de maintenance

```bash
# Lancer les tests
.venv/bin/python -m pytest

# Créer et appliquer une migration après modification des modèles
.venv/bin/python -m alembic revision --autogenerate -m "description du changement"
.venv/bin/python -m alembic upgrade head

# Traiter les relevés déjà présents dans la base locale
.venv/bin/python scripts/run_etl_once.py
```

## 9. Utiliser l'API

### Adresse et documentation interactive

En développement, l'API est accessible à l'adresse `http://localhost:8000`.
Toutes les routes métier sont préfixées par `/api/v1` et la documentation
OpenAPI interactive est disponible sur `http://localhost:8000/docs`.

La route de santé est publique :

```bash
curl http://localhost:8000/health
```

Réponse :

```json
{"status":"ok"}
```

### Authentification JWT

Toutes les routes sous `/api/v1`, sauf `POST /api/v1/auth/token`, nécessitent
un jeton Bearer. Connectez-vous avec un compte de démonstration en envoyant des
données `application/x-www-form-urlencoded` :

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=camille.admin&password=EnerVisionDemo2026!"
```

Réponse `200` :

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Conservez la valeur de `access_token` et transmettez-la dans l'en-tête
`Authorization` de chaque requête protégée :

```bash
TOKEN="collez-ici-la-valeur-de-access_token"
curl http://localhost:8000/api/v1/sites \
  -H "Authorization: Bearer $TOKEN"
```

Un identifiant ou mot de passe incorrect renvoie `401` :

```json
{"detail":"Incorrect username or password"}
```

Un jeton absent, invalide ou expiré renvoie `401`. Un jeton valide qui ne porte
pas le rôle nécessaire renvoie `403` avec `{"detail":"Insufficient permissions"}`.

### Rôles et accès

| Rôle | Accès |
|---|---|
| `user` / `data_analyst` | Lecture des sites, relevés, alertes, prévisions et statistiques |
| `operator` | Accès en lecture et création de relevés ou de sites |
| `admin` | Tous les droits, dont la gestion des utilisateurs |

### Référence des endpoints

| Méthode | Endpoint | Authentification | Description |
|---|---|---|---|
| `GET` | `/health` | Aucune | État de l'API |
| `POST` | `/api/v1/auth/token` | Aucune | Obtenir un jeton JWT |
| `GET` | `/api/v1/sites` | Tout utilisateur connecté | Lister les sites |
| `POST` | `/api/v1/sites` | `admin` ou `operator` | Créer un site |
| `GET` | `/api/v1/sites/{site_id}` | Tout utilisateur connecté | Détail d'un site |
| `GET` | `/api/v1/sites/{site_id}/current` | Tout utilisateur connecté | Dernier relevé enregistré pour un site |
| `GET` | `/api/v1/readings` | Tout utilisateur connecté | Lister les relevés, avec filtres optionnels |
| `POST` | `/api/v1/readings/sites/{site_id}` | `admin` ou `operator` | Ajouter un relevé pour un site |
| `GET` | `/api/v1/alerts` | Tout utilisateur connecté | Lister les alertes |
| `GET` | `/api/v1/predictions/sites/{site_id}/next` | Tout utilisateur connecté | Prévision calculée depuis l'historique local |
| `GET` | `/api/v1/stats/summary` | Tout utilisateur connecté | Indicateurs globaux du parc |
| `GET` | `/api/v1/users` | `admin` | Lister les utilisateurs |
| `POST` | `/api/v1/users` | `admin` | Créer un utilisateur |

### Sites

Lister les sites :

```bash
curl http://localhost:8000/api/v1/sites \
  -H "Authorization: Bearer $TOKEN"
```

Réponse `200` :

```json
[
  {
    "id": 1,
    "code": "LYO-01",
    "name": "Atelier Lyon Gerland",
    "city": "Lyon",
    "country": "France",
    "surface_m2": 4200.0,
    "subscribed_power_kw": 850.0
  }
]
```

Créer un site (rôle `admin` ou `operator`) :

```bash
curl -X POST http://localhost:8000/api/v1/sites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "BOR-01",
    "name": "Atelier Bordeaux Nord",
    "city": "Bordeaux",
    "country": "France",
    "surface_m2": 2500,
    "subscribed_power_kw": 430
  }'
```

Réponse `201` : la représentation JSON du site créé, au même format que la
réponse de liste. Un code de site déjà utilisé renvoie `409`.

Le détail est disponible avec `GET /api/v1/sites/1`. Le dernier relevé est
accessible avec `GET /api/v1/sites/1/current` et renvoie :

```json
{
  "id": 142,
  "site_id": 1,
  "recorded_at": "2026-09-01T10:00:00Z",
  "consumption_kwh_raw": 281.34,
  "consumption_kwh_imputed": null,
  "data_quality": "good",
  "null_reasons": null,
  "source": "seed"
}
```

Un identifiant de site inexistant renvoie `404` avec
`{"detail":"Site not found"}`.

### Relevés de consommation

Lister les relevés :

```bash
curl "http://localhost:8000/api/v1/readings?site_id=1&start_at=2026-09-01T00:00:00Z&end_at=2026-09-01T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

Les paramètres `site_id`, `start_at` et `end_at` sont optionnels. Les dates
utilisent le format ISO 8601, idéalement en UTC (`Z`). La réponse `200` est un
tableau de relevés triés du plus récent au plus ancien :

```json
[
  {
    "id": 101,
    "site_id": 1,
    "recorded_at": "2026-09-01T09:00:00Z",
    "consumption_kwh_raw": null,
    "consumption_kwh_imputed": 278.0,
    "data_quality": "partial",
    "null_reasons": ["scheduled_sensor_maintenance"],
    "source": "seed"
  }
]
```

Ajouter un relevé (rôle `admin` ou `operator`) :

```bash
curl -X POST http://localhost:8000/api/v1/readings/sites/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recorded_at": "2026-09-01T12:00:00Z",
    "consumption_kwh_raw": 315.7,
    "consumption_kwh_imputed": null,
    "data_quality": "good",
    "null_reasons": null
  }'
```

La réponse `201` reprend le relevé créé avec `id`, `site_id` et `source: "api"`.
Si `consumption_kwh_raw` est `null`, `null_reasons` est obligatoire. La valeur
brute est toujours conservée : une imputation éventuelle doit être écrite dans
`consumption_kwh_imputed`, jamais à la place de la valeur brute.

### Alertes, prévisions et statistiques

Alertes actives (valeur par défaut) :

```bash
curl "http://localhost:8000/api/v1/alerts?active_only=true" \
  -H "Authorization: Bearer $TOKEN"
```

Réponse `200` :

```json
[
  {
    "id": 1,
    "site_id": 2,
    "severity": "warning",
    "message": "Consommation elevee detectee sur le site Grenoble Sud.",
    "triggered_at": "2026-09-01T08:00:00Z",
    "is_active": true
  }
]
```

Passez `active_only=false` pour inclure les alertes inactives. Les niveaux de
sévérité sont `info`, `warning` et `critical`.

Prévision pour le prochain créneau :

```bash
curl http://localhost:8000/api/v1/predictions/sites/1/next \
  -H "Authorization: Bearer $TOKEN"
```

Réponse `200` :

```json
{
  "site_id": 1,
  "predicted_consumption_kwh": 304.35,
  "based_on_readings": 24
}
```

La prévision est une estimation calculée à partir des 24 derniers relevés
exploitables du site. Les statistiques globales sont récupérées ainsi :

```bash
curl http://localhost:8000/api/v1/stats/summary \
  -H "Authorization: Bearer $TOKEN"
```

Réponse `200` :

```json
{
  "site_count": 3,
  "reading_count": 144,
  "active_alert_count": 1,
  "average_consumption_kwh": 300.12
}
```

### Utilisateurs

Les routes utilisateurs sont réservées au rôle `admin`. Lister les utilisateurs :

```bash
curl http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN"
```

Réponse `200` :

```json
[
  {
    "id": 1,
    "username": "camille.admin",
    "email": "camille.martin@enervision.demo",
    "full_name": "Camille Martin",
    "is_active": true,
    "roles": [{"id": 1, "name": "admin"}]
  }
]
```

Créer un utilisateur :

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "lea.manager",
    "email": "lea.manager@example.test",
    "full_name": "Lea Manager",
    "password": "UnMotDePasseRobuste2026!",
    "role_names": ["operator", "user"]
  }'
```

La réponse `201` retourne l'utilisateur créé sans son mot de passe. Les champs
invalides renvoient `422`; un identifiant ou une adresse e-mail déjà utilisé(e)
renvoie `409`.

## 10. Conventions de contribution

- **Branches :** `EADL_2025_[VILLE]_G[N]/[feature-ou-tache]`
- **Commits :** clairs, atomiques — l'historique Git sert de preuve de
  contribution individuelle lors de l'évaluation.
- **Code :** linter configuré (à définir : ruff/flake8 + black), doc à jour
  systématiquement.
- **Pas de secrets en dur** dans le code — utiliser `.env` (voir
  `.env.example`) et exclu du versioning via `.gitignore`.

## 11. Ce que l'agent IA doit garder en tête en permanence

1. Ce projet sera évalué à l'oral avec des **questions adversariales**
   ("pourquoi pas X ?", "comment ça gère Y ?") — privilégier des choix
   simples, justifiables et documentés plutôt que des solutions complexes
   non maîtrisées.
2. Toute dépendance ou service tiers ajouté doit pouvoir être **justifié**
   (pas d'ajout "parce que ça marche" sans réflexion architecturale).
3. La gestion des données incomplètes/dégradées (NULL, `data_quality`) est
   un point d'attention central du projet — ne jamais la contourner
   silencieusement.
4. Le code doit rester **modulaire et testable** : respecter la séparation
   des couches définie en §4.
