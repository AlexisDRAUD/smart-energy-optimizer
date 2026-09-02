# Qualite du code

## Ce qui est en place

| Outil | Ce qu'il fait | Ou il tourne |
|---|---|---|
| ruff (lint) | detecte erreurs reelles, imports morts, nommage, pieges, secrets en dur | poste local, pre-commit, chaine d'integration |
| ruff (format) | met en forme, une seule facon d'ecrire pour toute l'equipe | idem |
| pre-commit | lance les controles avant chaque commit | poste local |
| eslint et prettier | equivalent pour le front | poste local et chaine d'integration |

La configuration est dans `pyproject.toml` a la racine, un seul fichier pour tout le depot.
Le linter donne donc le meme verdict chez chacun et dans la chaine d'integration, sinon les
demandes de fusion se transforment en discussions de virgules.

## Installation, une fois par personne

```bash
pip install ruff pre-commit
pre-commit install
```

A partir de la, un commit qui ne passe pas les controles est refuse localement, avant meme
d'arriver sur le depot.

## Commandes

```bash
ruff check .                 # signale les problemes
ruff check . --fix           # corrige ce qui se corrige tout seul
ruff format .                # met en forme
pre-commit run --all-files   # tout, sur tout le depot
```

## Produire le rapport de qualite

```bash
ruff check . --output-format=json > rapport-qualite.json
ruff check . --statistics
pytest --cov=packages --cov=services --cov-report=html
```

Le rapport de couverture se lit dans `htmlcov/index.html`. Ces fichiers ne sont pas commites,
ils sont produits a la demande et joints a la soutenance.

## Pourquoi ces regles

Les familles activees couvrent les erreurs reelles (variable non utilisee, import mort, nom
inconnu), l'ordre des imports, le nommage, les tournures obsoletes, les pieges classiques et
les motifs a risque de securite comme un secret ecrit en dur. Le depot etant public, cette
derniere famille n'est pas decorative.

Une regle est desactivee : l'interdiction de `assert`, qui n'a pas de sens dans les tests.

## Code modulaire

Trois regles simples, verifiables en relecture.

- Une fonction fait une chose. Si son nom contient "et", elle en fait deux.
- Le calcul et l'acces aux donnees sont separes. Une fonction qui lit la base et calcule en
  meme temps ne se teste pas sans base.
- Ce qui est partage par plusieurs services vit dans `packages/common`, et rien d'autre n'y va.
