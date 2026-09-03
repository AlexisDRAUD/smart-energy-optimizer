# Structure du dépôt

A quoi sert chaque dossier, et surtout ce qui n'a pas à y aller. Les dossiers qui ne font que
contenir d'autres dossiers (`services/`, `.github/`) ne sont pas listes.

## `docs/`

Toute la documentation du projet. Les contrats de donnees et d'API font foi, le reste explique
et justifie. C'est aussi le dossier que lisent les assistants de code.

## `packages/features/`

Le calcul des variables d'entrée du modèle, écrit une seule fois, importé à la fois par
l'entraînement (`services/ml`) et par le service (`services/backend`). Si les deux calculaient
la même variable de deux façons, le modèle se dégraderait en production sans qu'aucun test
n'échoue.

C'est sa seule raison d'être, et c'est le seul paquet partagé du dépôt.
N'y va pas : tout le reste. Ce dont un seul composant se sert reste chez lui, et deux
composants qui partagent du code sans cette raison-là devraient plutôt n'en faire qu'un.

## `services/backend/`

Le collecteur, l'ETL et l'API. Une seule image, lancée en plusieurs conteneurs avec des
commandes différentes. C'est le seul composant qui touche à la base, et il en porte le schéma.

- `app/collector/` interroge la source et écrit la réponse **telle quelle** dans la couche
  brute. Contient aussi les scripts d'amorçage. N'y va pas : la moindre transformation, ce qui
  est jeté ici est perdu définitivement.
- `app/etl/` lit la couche brute, contrôle, répare, agrège, écrit la couche transformée.
  Rejouable sur une fenêtre déjà traitée sans créer de doublon. N'y va pas : le calcul des
  variables du modèle, il est dans `packages/features`.
- `app/api/`, `app/crud/`, `app/schemas/`, `app/services/` : le backend HTTP. Expose les
  données, charge le modèle, calcule les seuils et les agrégats, émet les alertes. C'est le
  seul composant que le front interroge. N'y va pas : l'accès direct à la base depuis
  l'extérieur.
- `app/db/` les modèles SQLAlchemy, la session et les données de démonstration.
- `alembic/` les migrations. **Le schéma de la base n'existe que là.**

N'y va pas : le code d'entraînement, il est dans `services/ml` et n'a pas les mêmes
dépendances.

## `services/ml/`

Entraînement, évaluation, publication dans MLflow. Lancé à la demande, pas en permanence.
Produit un artefact versionné, pas un service. Image séparée du backend : ses dépendances sont
lourdes et ne servent qu'à lui.

Il lit la base en SQL direct et n'y écrit rien, donc il n'importe pas les modèles du backend.
N'y va pas : le code qui sert les prédictions, il est dans le backend.

## `services/web/`

Le dashboard React. Affiche et filtre.
N'y va pas : la logique metier. Aucun seuil, aucun agrégat, aucune règle. Une règle dupliquée
dans le front finit par diverger, et elle n'est testée nulle part.

## `infra/`

L'infrastructure décrite en code, pour la partie hébergée ailleurs.
N'y va pas : un secret, meme temporaire.

## `data/`

Les CSV fournis par le formateur, en local uniquement. Le dossier est exclu du dépôt, chacun
le crée chez lui. Le dépôt est public, aucune donnée ne s'y trouve.

## `.github/workflows/`

Les chaines d'intégration. Une par domaine : Python, front, sécurité.
N'y va pas : un secret en clair. Les valeurs sensibles passent par les secrets du depot.
