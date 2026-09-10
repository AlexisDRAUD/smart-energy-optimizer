# Service ML

Entraînement des modèles de prévision et serveur MLflow. Un modèle par site, horizon de deux heures.

La documentation de référence est [`ml.md`](../../docs/ml.md) : variables, découpage temporel,
métriques, registre, mise en service et pilotage.

## Entraîner

```bash
docker compose exec mlflow python /app/main.py              # tous les sites
docker compose exec mlflow python /app/main.py --site-id SITE001
```

Les arguments et leurs valeurs par défaut sont listés par `--help`. Les plus utiles sont
`--train-months`, `--holdout-months`, `--estimator` et `--n-estimators`.

## Le serveur

Le conteneur lance MLflow puis, si `ML_TRAIN_ON_START` vaut `1`, un entraînement avec les arguments
de `TRAIN_ARGS`. En production cette variable vaut `0` : l'entraînement y est déclenché
explicitement.

Le magasin de suivi est un SQLite du volume `mlflow_data`, les artefacts vont dans MinIO. Le port
n'est publié que sur la boucle locale, l'interface s'atteint par un tunnel SSH.

Le conteneur expose aussi une page `/training` qui permet de lancer un entraînement par site depuis
le navigateur.

## Structure

```
main.py            pipeline d entrainement, enregistrement et alias
start.py           demarrage du serveur puis entrainement optionnel
compare_models.py  comparaison de plusieurs regresseurs sur un site
ui/                page de lancement d entrainement dans MLflow
tests/             tests du pipeline et des variables
```

## Une règle à respecter

Les variables d'entrée du modèle sont calculées par `packages/features`, jamais recalculées ici.
C'est ce qui garantit que l'entraînement et le service voient exactement les mêmes colonnes, et la
signature enregistrée avec le modèle le vérifie au chargement.
