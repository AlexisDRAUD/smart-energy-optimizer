# Tests et qualité du code

## Lancer les tests

Les tests du backend ont besoin d'un vrai PostgreSQL. Ils créent et détruisent leur propre
base, `seo_test`, à côté de la base de travail : il suffit que `db` tourne.

**Dans un conteneur**, sans rien installer :

```bash
docker compose up -d db
docker compose run --rm --no-deps \
  -e TEST_DATABASE_URL="postgresql+psycopg://seo:<mot de passe>@db:5432/seo_test" \
  --entrypoint sh migrate -c "python -m pytest -q"
```

**Sur le poste**, après l'installation décrite dans `setup.md` :

```bash
docker compose up -d db
cd services/backend
JWT_SECRET_KEY=test-only-secret-with-at-least-32-characters \
TEST_DATABASE_URL=postgresql+psycopg://seo:<mot de passe>@127.0.0.1:5432/seo_test \
  ../../.venv/bin/python -m pytest -q
```

Les migrations sont appliquées sur cette base neuve avant chaque session : une migration cassée
est attrapée par la suite de tests, pas découverte par un coéquipier.

**Le front** :

```bash
cd services/web
npm ci
npm run test:coverage
```

## Couverture visée

| Zone | Cible | Pourquoi |
|---|---|---|
| Pipeline de données | environ 80 % des branches | c'est là que se cache la perte de données |
| API, inférence, règles | environ 70 % | contrat exposé |
| Dashboard | pas de seuil | le risque n'est pas là |

Un seuil unique pousse à écrire des tests inutiles sur le code d'affichage pour atteindre un
chiffre.

## Familles de tests

- **Unitaires.** Calcul des variables d'entrée, règles d'imputation, règles de recommandation,
  calcul des seuils.
- **Intégration.** Le collecteur écrit bien dans la couche brute, l'ETL est rejouable sans
  créer de doublon, l'API rend bien ce que le contrat annonce.
- **Qualité des données.** Contrôles sur les valeurs et les plages. **Ils ne bloquent pas le
  pipeline**, ils marquent l'anomalie. Bloquer transformerait un problème de qualité en perte
  de données.
- **Résilience.** Injection de pannes : source injoignable, base indisponible, conteneur
  arrêté.
- **Non fonctionnels.** Temps de réponse de l'API sur une fenêtre longue, durée d'un passage
  de l'ETL.

## Outils de qualité

| Outil | Ce qu'il fait | Où il tourne |
|---|---|---|
| ruff (lint) | erreurs réelles, imports morts, nommage, pièges, secrets en dur | poste, pre-commit, chaîne d'intégration |
| ruff (format) | met en forme, une seule façon d'écrire pour toute l'équipe | idem |
| pre-commit | lance les contrôles avant chaque commit | poste |
| eslint, prettier, tsc | équivalent pour le front | poste et chaîne d'intégration |

La configuration est dans `pyproject.toml` à la racine, un seul fichier pour tout le dépôt. Le
linter donne donc le même verdict chez chacun et dans la chaîne d'intégration, sinon les
demandes de fusion se transforment en discussions de virgules.

## Installation, une fois par personne

```bash
pip install ruff pre-commit
pre-commit install
```

À partir de là, un commit qui ne passe pas les contrôles est refusé localement, avant même
d'arriver sur le dépôt.

## Commandes

```bash
ruff check .                 # signale les problemes
ruff check . --fix           # corrige ce qui se corrige tout seul
ruff format .                # met en forme
pre-commit run --all-files   # tout, sur tout le depot
```

Sans installation locale, la version exacte de la chaîne d'intégration :

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12-alpine \
  sh -c "pip install -q ruff==0.16.5 && ruff check . && ruff format --check ."
```

## Produire le rapport pour la soutenance

```bash
ruff check . --output-format=json > rapport-qualite.json
ruff check . --statistics
pytest --cov=packages --cov=services --cov-report=html
```

Le rapport de couverture se lit dans `htmlcov/index.html`. Ces fichiers ne sont pas commités,
ils sont produits à la demande.

## Pourquoi ces règles

Les familles activées couvrent les erreurs réelles, l'ordre des imports, le nommage, les
tournures obsolètes, les pièges classiques et les motifs à risque de sécurité comme un secret
écrit en dur. Le dépôt étant public, cette dernière famille n'est pas décorative.

Une règle est désactivée : l'interdiction de `assert`, qui n'a pas de sens dans les tests.

## Code modulaire

Trois règles simples, vérifiables en relecture.

- Une fonction fait une chose. Si son nom contient « et », elle en fait deux.
- Le calcul et l'accès aux données sont séparés. Une fonction qui lit la base et calcule en
  même temps ne se teste pas sans base.
- Le calcul des variables du modèle vit dans `packages/features`, et rien d'autre n'y va.
