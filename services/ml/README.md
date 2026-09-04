# Service ML

Entrainement, evaluation et publication du modele dans MLflow.

## Variables d'environnement

- `DATABASE_URL` (obligatoire avec `--use-db`)
- `MLFLOW_TRACKING_URI` (optionnel, recommande en CI/prod)

Exemple:

```bash
export DATABASE_URL="postgresql://user:password@db-host:5432/enervision"
export MLFLOW_TRACKING_URI="http://mlflow-server:5000"
```

## Lancer l'entrainement

Depuis PostgreSQL:

```bash
python services/ml/main.py --use-db --train-months 22 --holdout-months 2
```

Depuis CSV (compatibilite):

```bash
python services/ml/main.py --csv services/ml/donnees.csv
```

Le modele est enregistre dans le Model Registry MLflow sous:

- `EnerVision_RF_Predictor` (nom registre)

## Exposer le modele

### Option A: MLflow serve (MVP rapide)

```bash
export MLFLOW_TRACKING_URI="http://mlflow-server:5000"
mlflow models serve -m "models:/EnerVision_RF_Predictor/latest" -p 5001 --host 0.0.0.0
```

### Option B: FastAPI (integration applicative)

Un exemple minimal est disponible dans `services/ml/predict_api.py`.

Lancement:

```bash
pip install fastapi uvicorn
uvicorn services.ml.predict_api:app --host 0.0.0.0 --port 8000
```

## Automatisation cron (VM)

Exemple crontab:

```cron
0 2 * * * /chemin/vers/venv/bin/python /chemin/vers/repo/services/ml/main.py --use-db --train-months 22 --holdout-months 2 >> /var/log/enervision/train.log 2>&1
```
