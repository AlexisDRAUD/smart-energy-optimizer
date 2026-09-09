# Configuration

Un seul fichier de réglages pour tout le dépôt, le `.env` de la racine. Il n'est jamais
commité. `.env.example` en donne la liste avec des valeurs de travail.

C'est le **seul** endroit où le poste local et la VM diffèrent. Il n'y a qu'un
`docker-compose.yml`, et il ne contient aucune valeur propre à un environnement.

## Qui lit ce fichier

| Lecteur | Ce qu'il en prend |
|---|---|
| `docker compose` | les `${...}` du `docker-compose.yml`, qui recopie les variables dans les conteneurs |
| `app/config.py` | le même fichier, quand le backend tourne hors docker (Alembic, pytest) |
| Vite | uniquement les variables préfixées `VITE_`, au moment du build du front |

Une variable absente du bloc `environment:` du `docker-compose.yml` **n'atteint jamais les
conteneurs**, même si elle est dans le `.env`. Le conteneur tourne alors sur la valeur par
défaut du code, sans que rien ne le signale. En ajouter une demande donc deux gestes :
la déclarer dans `.env.example` et l'ajouter au bloc `environment:`.

## Base de données

| Variable | Défaut | Rôle |
|---|---|---|
| `POSTGRES_USER` | `seo` | l'utilisateur créé au premier démarrage du conteneur `db` |
| `POSTGRES_PASSWORD` | — | **secret**, à générer par poste |
| `POSTGRES_DB` | `seo` | le nom de la base |
| `DB_HOST_PORT` | `5432` | port publié sur la machine hôte, à changer si un PostgreSQL local occupe déjà 5432 |
| `DATABASE_URL` | — | utilisée **uniquement hors docker**, par Alembic et pytest. Sous compose, elle est fabriquée à partir des trois variables ci-dessus et pointe vers l'hôte `db` |
| `DATABASE_WAIT_SECONDS` | `30` | délai que `migrate` accorde à PostgreSQL avant d'abandonner |

PostgreSQL fige les identifiants à la **toute première** initialisation du volume. Changer
`POSTGRES_PASSWORD` sur un volume existant ne change rien et casse la connexion : il faut un
`docker compose down -v`.

## Source de données

| Variable | Défaut | Rôle |
|---|---|---|
| `SOURCE_API_BASE_URL` | `http://127.0.0.1:8000` | l'API du formateur. Jamais en dur dans le code |

Le défaut du code ne vaut que pour un backend lancé hors docker sur la même machine que la
source. Depuis un conteneur, `127.0.0.1` désigne le conteneur lui-même : il faut l'adresse
réelle de la machine qui héberge la source.

## Collecteur

| Variable | Défaut | Rôle |
|---|---|---|
| `COLLECTOR_INTERVAL_SECONDS` | `60` | temps de sommeil entre deux passages |
| `BACKFILL_DAYS` | `7` | profondeur de la reprise d'historique au premier démarrage |

`BACKFILL_DAYS` se paie au démarrage : la source rend une mesure par minute, donc 1440 lignes
par jour et par site. À 7 jours et 7 sites, c'est 70 560 lignes, une centaine d'appels HTTP,
et une dizaine de secondes. Le coût est linéaire, une profondeur de 30 jours multiplie tout
par quatre.

## ETL

| Variable | Défaut | Rôle |
|---|---|---|
| `ETL_INTERVAL_SECONDS` | `60` | temps de sommeil entre deux passages |
| `ETL_BATCH_SIZE` | `1000` | lignes brutes lues par requête à l'intérieur d'une fenêtre |
| `ETL_WINDOW_OVERLAP_MINUTES` | `2` | de combien chaque passage repart avant la borne du précédent |

`ETL_WINDOW_OVERLAP_MINUTES` n'existe que pour rattraper une ligne dont la transaction n'était
pas terminée au moment de la lecture. Nos écritures durent des millisecondes, deux minutes
laissent mille fois la marge. **Ce n'est pas la fenêtre de réparation**, qui est plus large et
porte sur une autre table. Une valeur trop grande coûte cher : après une reprise d'historique,
les 70 000 lignes portent toutes le même horodatage de réception, et une fenêtre de trente
minutes les relit entièrement à chaque passage.

## Réparation des valeurs nulles

| Variable | Défaut | Rôle |
|---|---|---|
| `IMPUTATION_WINDOW_MINUTES` | `30` | profondeur de `readings` revisitée à chaque passage |
| `IMPUTATION_PROFILE_REFRESH_HOURS` | `24` | âge au-delà duquel le profil d'un site est recalculé |

La stratégie est décrite dans `adr/ADR-2026-09-04-strategie-imputation-consommation.md`.

## API

| Variable | Défaut | Rôle |
|---|---|---|
| `API_PORT` | `8080` | port publié sur la machine hôte, limité à `127.0.0.1` |
| `JWT_SECRET_KEY` | — | **secret**, 32 caractères minimum. Le compose refuse de démarrer sans |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | durée du jeton présenté à chaque appel |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | durée du cookie de session |
| `COOKIE_SECURE` | `false` | à passer à `true` derrière HTTPS |
| `SEED_USER_PASSWORD` | — | mot de passe des trois comptes de démonstration |
| `PREDICTION_REFRESH_INTERVAL_SECONDS` | `60` | cadence de la boucle de prédiction de l'API |

`COOKIE_SECURE=true` sans HTTPS empêche le navigateur d'envoyer le cookie de session, et la
connexion échoue silencieusement au premier renouvellement de jeton.

## Superviseur

Lues par `app/supervisor/config.py`, sous le préfixe `SUPERVISOR_`, par le seul conteneur
`supervisor`. Les valeurs par défaut sont les décisions du lot (`ml-supervision.md`), pas des
réglages techniques : ce sont des valeurs de départ, à calibrer sur des données réelles.

| Variable | Défaut | Rôle |
|---|---|---|
| `SUPERVISOR_INTERVAL_SECONDS` | `300` | temps de sommeil entre deux tours |
| `SUPERVISOR_DECISION_WINDOW_HOURS` | `168` | fenêtre de la MAE qui juge la dérive (7 jours) |
| `SUPERVISOR_ALERT_WINDOW_HOURS` | `24` | fenêtre de la MAE qui prévient, sans décider |
| `SUPERVISOR_GRACE_HOURS` | `24` | données exigées depuis la première notation avant tout verdict |
| `SUPERVISOR_LOCK_HOURS` | `24` | écart minimal entre deux lancements pour un même site |
| `SUPERVISOR_MAX_MODEL_AGE_DAYS` | `7` | âge au-delà duquel un modèle est réentraîné même sans dérive |
| `SUPERVISOR_MAE_TOLERANCE` | `1.5` | seuil de repli = MAE holdout × tolérance, quand le run MLflow n'a pas de `drift_threshold_mae` |

Toute valeur nulle ou négative fait refuser le démarrage. Le superviseur prend en plus à
`app/config.py` ce qu'il partage avec le reste du backend : `DATABASE_URL`,
`MLFLOW_TRACKING_URI` et le préfixe des modèles. Sans `MLFLOW_TRACKING_URI`, aucun site n'a de
seuil et la supervision est inactive partout, avec un avertissement au démarrage.

## Front

| Variable | Défaut | Rôle |
|---|---|---|
| `WEB_BIND` | `127.0.0.1` | interface d'écoute du dashboard |
| `WEB_PORT` | `80` | port publié |
| `VITE_BACK_API_URL` | vide | à laisser vide tant que le front passe par le proxy nginx |

`WEB_BIND` à `127.0.0.1` limite l'accès à la machine hôte, ce qui convient en local. Sur une
machine partagée, il faut `0.0.0.0` pour que le dashboard soit joignable depuis le réseau.

`VITE_BACK_API_URL` est lue **au moment du build** de l'image `web`, pas au démarrage du
conteneur. La changer impose un `docker compose build web`.

## Réglages qui ne passent pas par le `.env`

Six valeurs restent dans `app/config.py` : `app_name`, `api_v1_prefix`, `jwt_algorithm`,
`prediction_horizon_minutes`, `local_model_name`, `local_model_version`. Elles n'ont pas de
raison de différer entre le poste local et la VM. Les rendre configurables ajouterait six
façons de casser la configuration sans rien apporter.
