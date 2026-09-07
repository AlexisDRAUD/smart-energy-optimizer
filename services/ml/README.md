# Service ML

Entrainement, evaluation et publication des modeles dans MLflow.

## Variables d'environnement

- `DATABASE_URL` (obligatoire avec `--use-db`)
- `MLFLOW_TRACKING_URI` (recommande)

## Entrainement

Mode base PostgreSQL (`readings` + `sites`) :

```bash
python services/ml/main.py --use-db --horizon-minutes 120
```

Mode CSV (fallback local) :

```bash
python services/ml/main.py --csv services/ml/donnees.csv
```

Le script entraine **un modele par site** et enregistre chaque modele sous :

- `EnerVision_RF_Predictor_<SITE_ID>`

Puis il met a jour l'alias de registre `production` (option desactivable avec
`--no-production-alias`).

## Exposition en production

Le service de prediction est dans `services/backend` (pas de serveur separe dans
`services/ml`).

## Automatisation

- GitHub Actions `train.yml` : execution manuelle sur runner `self-hosted` ayant
  acces reseau a la base.
- Cron VM : possible via crontab sur la machine qui heberge la base/MLflow.

## Test local avec docker-compose

Le repository fournit un service `mlflow` dans `docker-compose.yml` pour tester
localement un serveur MLflow (tracking + artifact store). Procédure minimale :

1. Démarrer la base et le serveur MLflow :

```bash
# démarre PostgreSQL et MLflow (construit l'image services/ml si nécessaire)
docker compose up -d db mlflow
```

2. Appliquer les migrations et données de démonstration :

```bash
# lance le job qui applique les migrations (s'arrête lorsqu'il a fini)
docker compose up migrate
```

3. Lancer (optionnel) l'API et le front :

```bash
docker compose up -d api web
```

4. Entraîner et enregistrer les modèles dans MLflow (exécution «one-shot» dans
   le conteneur contenant les dépendances ML) :

```bash
# depuis la racine du repo
# remplace --train-months/--holdout-months selon vos besoins
docker compose run --rm mlflow python main.py --use-db --train-months 22 --holdout-months 2
```

5. Accéder à l'interface MLflow : http://127.0.0.1:5000

Les artefacts (artéfacts MLflow + sqlite backend store) sont persistés dans le
volume Docker `mlflow_data`.

Remarques :
- Le backend attend la variable d'environnement `DATABASE_URL` ; docker-compose
  injecte la connexion au service `db` par défaut. Pour pointer un MLflow
  distant, définissez `MLFLOW_TRACKING_URI` dans votre `.env`.
- Pour lancer l'entraînement depuis l'image ML (hors docker compose) utilisez
  l'image construite par `services/ml/Dockerfile`.
