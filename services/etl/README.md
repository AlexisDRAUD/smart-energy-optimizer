# ETL local EnerVision

Cette première version lit un tableau de mesures depuis un fichier JSON, valide chaque ligne
indépendamment, puis charge les lignes valides dans une base SQLite locale. Le payload JSON
d'origine est conservé pour la traçabilité. La clé `(site_id, timestamp)` rend les relances
idempotentes.

Le découpage `extract`, `transform`, `load` et `main` permet de remplacer ultérieurement la
source JSON par l'API mock et SQLite par PostgreSQL sans réécrire les validations.

## Installation

Depuis `services/etl` avec Python 3.12 :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Exécution

Le fichier de démonstration contient quatre lignes valides, dont une mesure incomplète, et une
ligne volontairement invalide. Les chemins par défaut sont indépendants du dossier courant.

```powershell
python -m etl.main
```

Pour choisir les chemins :

```powershell
python -m etl.main --input fixtures/demo_readings.json --database data/local.sqlite3
```

La base par défaut est créée dans `data/enervision_etl.sqlite3`. Une ligne invalide est
journalisée puis ignorée sans interrompre le lot.

## Tests

```powershell
python -m pytest tests
```

La documentation de l'API mock confirme que les futures extractions pourront utiliser
`GET /api/v1/sites/{site_id}/current` ou `GET /api/v1/readings`.
