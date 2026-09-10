# Backend

Une seule image, cinq rôles. L'API REST, le collecteur, l'ETL, le worker de prévision et le
superviseur partagent le même code, la même base et la même cadence de livraison, et tournent dans
des conteneurs séparés.

La documentation de référence est dans [`../../docs/`](../../docs/). Ce fichier ne couvre que ce qui
est propre au développement de ce service.

| Sujet | Document |
|---|---|
| Vue d'ensemble et étages de données | [`architecture.md`](../../docs/architecture.md) |
| Routes, paramètres, codes d'erreur | [`api-contract.md`](../../docs/api-contract.md) |
| Tables, colonnes, contraintes | [`data-contract.md`](../../docs/data-contract.md) |
| Variables d'environnement | [`configuration.md`](../../docs/configuration.md) |
| Exploitation et diagnostic | [`runbook.md`](../../docs/runbook.md) |

## Structure

```
app/api/          routes, dependances, controle d acces
app/collector/    boucle de collecte et reprise d historique
app/etl/          transformation, imputation, qualite
app/services/     logique metier de l API
app/supervisor/   surveillance de l erreur du modele
app/db/           modeles ORM, session, comptes de demarrage
model/            worker de prevision, chargement du modele MLflow
alembic/          migrations
scripts/          demarrage des conteneurs
tests/            suite de tests
```

## Lancer

Le service se lance normalement par le compose de la racine. Pour travailler hors docker :

```bash
cd services/backend
python -m venv .venv && source .venv/bin/activate
pip install -e ../../packages/features -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

`DATABASE_URL` doit pointer vers une base PostgreSQL joignable. La documentation interactive est sur
`http://localhost:8080/docs`.

Les commandes des autres rôles :

```bash
python -m app.collector            # collecteur
python -m app.collector.backfill   # reprise d historique
python -m app.etl --once           # un passage d ETL
python -m model.predict --once     # un passage de prevision
python -m app.supervisor           # superviseur
```

## Tests

La suite exige un vrai PostgreSQL et recrée une base dédiée. Voir
[`tests-et-qualite.md`](../../docs/tests-et-qualite.md).

```bash
pytest --cov=app --cov-report=term-missing
```

## Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Le schéma n'existe que dans `alembic/versions/`. Aucun script SQL n'est joué par l'image PostgreSQL
au premier démarrage.

## Règles de contribution

- Le SQL écrit à la main est autorisé, mais **toujours paramétré**. Aucune valeur n'est interpolée
  dans une chaîne de requête.
- La couche brute est en insertion seule. Aucun code ne met à jour ni ne supprime dans
  `raw_readings` et `raw_snapshots`.
- Les variables du modèle sont calculées par `packages/features` et nulle part ailleurs, pour que
  l'entraînement et le service ne divergent jamais.
- Une route qui modifie quelque chose déclare le rôle qu'elle exige.
