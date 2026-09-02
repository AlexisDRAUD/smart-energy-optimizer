# Structure du dépôt

A quoi sert chaque dossier, et surtout ce qui n'a pas à y aller. Les dossiers qui ne font que
contenir d'autres dossiers (`services/`, `.github/`) ne sont pas listes.

## `docs/`

Toute la documentation du projet. Les contrats de donnees et d'API font foi, le reste explique
et justifie. C'est aussi le dossier que lisent les assistants de code.

## `packages/common/`

Le code utilise par plusieurs services, écrit une seule fois. Surtout le calcul des variables
d'entrée du modèle, importe a la fois par l'entrainement et par l'API. Si les deux calculaient
la meme variable de deux façons, le modèle se dégraderait en production sans qu'aucun test
n'échoue.
N'y va pas : ce dont un seul service se sert.

## `services/collector/`

Interroge la source et écrit la réponse **telle quelle** dans la couche brute. Contient aussi
les deux scripts d'amorçage, l'import des CSV et la reprise unique de l'historique.
Tourne en permanence, une lecture par minute.
N'y va pas : la moindre transformation. Ce qui est jeté ici est perdu définitivement.

## `services/etl/`

Lit la couche brute, contrôle, répare, agrège, écrit la couche transformée. Tourne toutes les
minutes, sur une fenêtre glissante de trente minutes, et peut être rejoué sur une fenêtre déjà
traitée sans créer de doublon.
N'y va pas : le calcul des variables d'entrée du modèle, il est dans le paquet commun.

## `services/ml/`

Entrainement, évaluation, publication dans MLflow. Lancé à la demande, pas en permanence.
Produit un artefact versionné, pas un service.
N'y va pas : le code qui sert les prédictions, il est dans l'API.

## `services/api/`

Le backend. Expose les données, charge le modèle au démarrage, calcule les seuils, les
agrégats et les recommandations, émet les alertes. C'est le seul composant que le front
interroge.
N'y va pas : l'accès direct a la base depuis l'exterieur.

## `services/web/`

Le dashboard React. Affiche et filtre.
N'y va pas : la logique metier. Aucun seuil, aucun agrégat, aucune règle. Une règle dupliquée
dans le front finit par diverger, et elle n'est testée nulle part.

## `db/migrations/`

Les fichiers SQL qui créent et font évoluer le schema. **Le schema de la base n'existe que
la.** Personne ne crée une table à la main, sinon la base distante et celle de chaque poste
divergent en deux jours.
N'y va pas : des données. Les migrations créent des structures, pas du contenu.

## `infra/`

L'infrastructure décrite en code, pour la partie hébergée ailleurs.
N'y va pas : un secret, meme temporaire.

## `data/`

Les CSV fournis par le formateur, en local uniquement. Le dossier est exclu du dépôt, chacun
le crée chez lui. Le dépôt est public, aucune donnée ne s'y trouve.

## `.github/workflows/`

Les chaines d'intégration. Une par domaine : Python, front, sécurité.
N'y va pas : un secret en clair. Les valeurs sensibles passent par les secrets du depot.
