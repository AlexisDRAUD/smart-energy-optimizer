# ETL local EnerVision

## Objectif

Ce prototype permet de valider localement le pipeline ETL avec des données fictives :

```text
JSON local → validation Pydantic → SQLite
```

SQLite sert uniquement aux tests locaux. L’architecture cible utilisera PostgreSQL :

```text
API mock → collecteur → raw_readings → ETL → données nettoyées → ML
```

## Fonctionnement

L’ETL exécute trois étapes :

* **Extract** : lecture de `fixtures/demo_readings.json` ;
* **Transform** : validation et normalisation des mesures avec Pydantic ;
* **Load** : insertion des mesures valides dans SQLite.

Une ligne invalide est journalisée sans interrompre le traitement. Les valeurs manquantes ne sont pas imputées et le payload source est conservé pour assurer sa traçabilité.

L’unicité repose sur le couple `site_id + timestamp` : rejouer le même fichier ne crée donc aucun doublon.

## Installation

Depuis la racine du dépôt, avec Python 3.12 :

```bash
cd services/etl
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m pip install ruff
```

## Exécution

```bash
./.venv/Scripts/python.exe -m etl.main
```

La base est créée automatiquement dans :

```text
data/enervision_etl.sqlite3
```

Pour repartir d’une base vide :

```bash
rm -i data/enervision_etl.sqlite3
```

La première exécution doit produire :

```text
lues=5 valides=4 rejetées=1 insérées=4 doublons_ignorés=0
```

Une seconde exécution du même fichier doit produire :

```text
lues=5 valides=4 rejetées=1 insérées=0 doublons_ignorés=4
```

La cinquième mesure est volontairement invalide (`power_factor = 1.4`) afin de vérifier qu’une mauvaise ligne est rejetée sans bloquer les autres.

## Tests et qualité

```bash
./.venv/Scripts/python.exe -m pytest tests -v
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m ruff format --check .
```

La base SQLite générée et l’environnement `.venv` sont ignorés par Git. Le fichier JSON de démonstration ne contient aucune donnée réelle.

## Limites actuelles

Cette version ne se connecte pas encore à l’API mock, PostgreSQL, S3 ou au modèle ML et ne possède pas de planification automatique.

La prochaine étape sera de lire les données brutes depuis PostgreSQL, puis de charger les mesures nettoyées dans les tables prévues pour le ML.
