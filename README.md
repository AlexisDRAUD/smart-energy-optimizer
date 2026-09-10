# EnerVision, Smart Energy Optimizer

Plateforme de suivi et de prévision de la consommation électrique d'un parc de sites. Elle collecte
les mesures d'une API source à la minute, les valide, les stocke par étages, en tire des indicateurs
de qualité, prévoit la consommation à deux heures par un modèle entraîné par site, et présente le
tout dans un dashboard.

Projet de formation EADL, RNCP39765.

## L'application déployée

`http://10.138.200.30`, sur une VM du Proxmox de l'école. Le déploiement est automatique à chaque
fusion dans `main`, voir `docs/deploiement.md`.

## Démarrer sur un poste

```bash
cp .env.example .env
# renseigner au minimum POSTGRES_PASSWORD, JWT_SECRET_KEY, SEED_USER_PASSWORD,
# MINIO_ROOT_USER, MINIO_ROOT_PASSWORD et SOURCE_API_BASE_URL
docker compose up -d
```

Le dashboard répond sur `http://localhost`, l'API sur `http://localhost:8080/docs`. Le premier
démarrage joue les migrations, crée les comptes et reprend l'historique, il prend donc plus de temps
que les suivants. Détail dans `docs/setup.md`.

## Ce qui tourne

Neuf conteneurs. Cinq partagent la même image backend avec des commandes différentes.

| | |
|---|---|
| `db` | PostgreSQL 16 |
| `migrate` | migrations, comptes, reprise d'historique, puis s'arrête |
| `api` | API REST, authentification, agrégats |
| `web` | nginx, sert le front et relaie `/api/` |
| `collector` | interroge la source toutes les 60 s |
| `etl` | transforme le brut toutes les 60 s |
| `model` | écrit les prévisions toutes les 60 s |
| `supervisor` | surveille l'erreur du modèle toutes les 300 s |
| `mlflow` + `minio` | suivi des entraînements et stockage des artefacts |

## D'où viennent les données

D'une API fournie par le formateur, sur le réseau de l'école. Deux usages distincts : une reprise
d'historique au premier démarrage, puis une lecture de l'instant présent toutes les minutes. Les
référentiels, l'état des capteurs et les alertes sont collectés de la même façon.

Rien n'est inventé. Aucune donnée de démonstration n'est insérée au démarrage, et l'interface
n'affiche que ce que l'API renvoie.

## Documentation

Tout est dans [`docs/`](docs/), avec un index qui indique quel document répond à quel livrable :
[`docs/README.md`](docs/README.md).

Les entrées les plus utiles pour commencer :

- [`docs/architecture.md`](docs/architecture.md), la vue d'ensemble
- [`docs/setup.md`](docs/setup.md), installer et lancer
- [`docs/runbook.md`](docs/runbook.md), exploiter et diagnostiquer
- [`docs/rapport-securite.md`](docs/rapport-securite.md), ce qui est protégé et ce qui ne l'est pas

## Organisation du dépôt

```
services/backend   API, collecteur, ETL, worker de prevision, superviseur
services/web       front React
services/ml        entrainement et serveur MLflow
packages/features  calcul des variables du modele, partage entrainement et service
infra/ansible      infrastructure comme code
docs/              documentation
```
