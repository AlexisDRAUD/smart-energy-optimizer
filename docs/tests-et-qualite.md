# Tests et qualité

Complète `ci.md`, qui décrit la chaîne. Ce document décrit les suites, les outils et ce qu'ils
couvrent réellement.

## Les suites

| Suite | Où | Combien | Ce qu'elle vérifie |
|---|---|---|---|
| Backend | `services/backend/tests/` | 28 fichiers, environ 164 tests | API, collecteur, ETL, imputation, qualité, prévision, superviseur |
| Modèle | `services/ml/tests/` | 3 fichiers, environ 18 tests | pipeline d'entraînement et calcul des variables |
| Front | `services/web/tests/` | 12 fichiers, environ 49 tests | rendu des pages, appels, états d'erreur, graphique |

Les suites du service ML ne sont pas jouées par la chaîne d'intégration, elles se lancent à la main.

## Le backend exige une vraie base

La suite ne remplace pas PostgreSQL par un double. Elle recrée une base dédiée, joue les migrations
Alembic, insère le jeu de données de test, puis supprime la base en fin de session. Une garde vérifie
d'abord que l'URL visée est bien une base de test, pour qu'une variable mal réglée ne puisse pas
effacer une base de travail.

Le choix est volontaire. Une grande partie du comportement du projet vit dans le schéma :
contraintes d'unicité qui rendent les écritures idempotentes, colonnes générées, contraintes de
vérification sur les énumérations. Un double en mémoire validerait du code qui échouerait en base.

```bash
cd services/backend
pytest --cov=app --cov-report=term-missing
```

## Le front

```bash
cd services/web
npm run lint          # eslint
npm run typecheck     # tsc --noEmit sur le code
npm run typecheck:test # tsc --noEmit sur les tests
npm run test:coverage # jest
```

Jest avec jsdom et Testing Library. Les tests portent sur ce que l'utilisateur voit, pas sur l'état
interne des composants : présence des valeurs, message de chargement, message d'erreur avec bouton
de reprise, conservation des dernières données reçues quand un rafraîchissement échoue.

## Qualité de code

**Ruff** pour Python, configuré à la racine dans `pyproject.toml` : ligne à 100 caractères, cible
3.12, et un ensemble de règles qui va au-delà du style, erreurs courantes, tri des imports,
conventions de nommage, modernisation, pièges classiques, simplifications, chemins de fichiers, et
un jeu de règles de sécurité. Les règles de sécurité sont désactivées dans les tests, où l'usage
d'assertions est normal.

**ESLint et TypeScript** pour le front, en configuration plate, avec le mode strict de TypeScript.

**Pre-commit** attrape avant le commit ce que la chaîne refuserait ensuite : ruff et son formateur,
espaces de fin de ligne, fin de fichier, validité des YAML, taille des fichiers ajoutés, marqueurs de
conflit non résolus, et refus d'une clé privée.

```bash
pip install pre-commit && pre-commit install
```

## Ce que les tests couvrent, et ce qu'ils ne couvrent pas

Trois familles sont bien couvertes et se démontrent. Les règles de validation et de rejet de l'ETL,
ligne par ligne. Les propriétés d'idempotence, relire une fenêtre déjà traitée ne crée pas de
doublon. Et les cas d'erreur de l'API, site inconnu, paramètres hors bornes, rôle insuffisant.

Ce qui n'est pas couvert :

- **Pas de test de bout en bout.** Personne ne vérifie automatiquement qu'un utilisateur peut se
  connecter et voir un graphique. Le premier scénario à écrire serait exactement celui-là, avec un
  outil pilotant un navigateur, joué après le déploiement plutôt que dans la chaîne.
- **Pas de test de charge.**
- **Pas de seuil minimal de couverture.** La couverture est mesurée et publiée, aucune valeur
  plancher ne fait échouer un job. Un seuil posé sans réflexion pousse à écrire des tests qui
  couvrent sans vérifier, mais l'absence de plancher laisse la couverture dériver sans que personne
  ne le voie.
- **Pas d'analyse de complexité ni de duplication.** Ruff et ESLint ne les mesurent pas.
- **Pas de test de propriété ni de test de mutation.**

## Indicateurs suivis

Ceux qui sont produits automatiquement à chaque exécution de la chaîne :

| Indicateur | Où le lire |
|---|---|
| Couverture backend | artefact `backend-coverage`, `coverage.xml` |
| Couverture front | artefact `web-coverage`, `lcov.info` |
| Vulnérabilités par image et par sévérité | résumé du job et artefact `trivy-image-reports-<sha>` |
| Durée de la chaîne | onglet Actions |

Ceux qui se relèvent à la main et qui manquent aujourd'hui : nombre de demandes de fusion ouvertes
et âge de la plus ancienne, retard des branches en commits, délai entre l'ouverture d'une PR et sa
fusion.
