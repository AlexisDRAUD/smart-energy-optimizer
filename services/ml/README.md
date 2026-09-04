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
