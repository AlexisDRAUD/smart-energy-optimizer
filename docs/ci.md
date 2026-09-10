# Chaîne d'intégration et de déploiement

Livrable EC03. Décrit la chaîne telle qu'elle est dans `.github/workflows/`.

Trois fichiers de workflow existent. `ci.yml` porte l'intégration continue et le déploiement.
`train.yml` et `mlflow_pipeline.yml` concernent l'entraînement, ils sont décrits dans `ml.md`.

## Déclenchement

`ci.yml` tourne sur `push` et sur `pull_request` vers `main` et `dev`. Aucune étape ne se déclenche
ailleurs : une branche de travail ne consomme des minutes qu'au moment de la demande de fusion.

Deux versions d'outils sont figées en tête de fichier pour les jobs de qualité, `PYTHON_VERSION`
à 3.12 et `NODE_VERSION` à 24. Les images gardent leurs propres versions de base dans leurs
`Dockerfile` et sont contrôlées séparément par Trivy.

## Les sept jobs

| Job | Dépend de | Quand | Où | Ce qu'il fait |
|---|---|---|---|---|
| `backend-lint` | rien | toujours | ubuntu-latest | `ruff check .` puis `ruff format --check .` sur tout le dépôt |
| `backend-test` | `backend-lint` | toujours | ubuntu-latest | `pytest` avec couverture, contre un vrai PostgreSQL 16 |
| `web-lint` | rien | toujours | ubuntu-latest | `eslint` puis `tsc --noEmit` |
| `web-test` | `web-lint` | toujours | ubuntu-latest | typage des tests puis Jest avec couverture |
| `docker-security` | `backend-test`, `web-test` | PR, ou push sur `dev` ou `main` | ubuntu-latest | construit et scanne les trois images avec Trivy |
| `docker-publish` | `docker-security` | push sur `dev` ou `main` | ubuntu-latest | publie dans GHCR les images déjà scannées |
| `deploy` | `docker-publish` | push sur `main` seulement | runner auto-hébergé | rejoue le playbook Ansible sur la VM |

```
backend-lint ──> backend-test ──┐
                                ├──> docker-security ──> docker-publish ──> deploy (main)
web-lint     ──> web-test    ───┘
```

Les deux domaines avancent en parallèle. À l'intérieur d'un domaine, les tests attendent le lint :
inutile de réserver un PostgreSQL ou de réinstaller les dépendances npm pour un code que le linter
refuse déjà.

## Analyse de vulnérabilités

`docker-security` construit localement les trois images, backend, web et mlflow, taguées par
l'empreinte du commit, puis Trivy analyse leurs paquets système et leurs bibliothèques. Le job ne
reçoit que `contents: read` et ne se connecte à aucun registre.

Paramètres identiques pour les trois : sévérités `HIGH` et `CRITICAL`, vulnérabilités sans
correctif comprises (`ignore-unfixed: false`), sortie JSON. L'action est épinglée par empreinte de
commit et non par étiquette, une étiquette pouvant être redéplacée sur un autre code.

Trois étapes exploitent ces rapports. Une validation `jq` vérifie que chaque fichier a bien la
structure attendue et échoue sinon, ce qui empêche un scan raté de passer pour un scan propre. Un
résumé affiche les compteurs par image dans le récapitulatif du job. Les rapports sont publiés en
artefact `trivy-image-reports-<sha>`, conservés trente jours, et constituent l'annexe factuelle du
rapport de sécurisation.

**La politique bloquante ne porte que sur `backend` et `web`.** Une seule vulnérabilité `CRITICAL`
sur l'une des deux fait échouer le job. L'image mlflow est scannée et son rapport publié, mais elle
ne bloque pas : son serveur n'écoute que sur l'adresse locale de la VM et sa pile scientifique
remonte des vulnérabilités sans correctif disponible. La décision est commentée dans le workflow,
avec sa condition de levée, lire le premier rapport et écrire les exceptions.

## Publication

Sur un push vers `dev` ou `main`, les images qui ont passé le contrôle sont exportées en artefact
intermédiaire conservé un jour. `docker-publish` recharge **exactement ces images**, obtient seul la
permission `packages: write`, se connecte à GHCR et publie. Une image refusée par la politique Trivy
ne peut donc pas être publiée.

Deux étiquettes par image :

- l'empreinte du commit, immuable, qui sert à figer une version et à revenir en arrière,
- le nom de la branche, mobile, que la VM suit.

Comme une étiquette mobile ne dit pas quel commit tourne, les trois images portent deux labels OCI,
`org.opencontainers.image.revision` et `org.opencontainers.image.source`. Un `docker inspect` rend
donc l'empreinte exacte du code en service :

```bash
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
  ghcr.io/alexisdraud/smart-energy-optimizer-backend:main
```

## Déploiement

Le job `deploy` ne tourne que sur un push vers `main`, sur le runner auto-hébergé installé sur la
VM. GitHub n'entre jamais sur la machine, c'est le runner qui sort. Aucune clé SSH n'est confiée au
dépôt et la connexion Ansible est locale.

Étapes, dans l'ordre :

1. Récupération du dépôt au commit qui a déclenché l'exécution.
2. Écriture du secret de dépôt `PROD_ENV` dans un fichier temporaire, avec `umask 077` puisque le
   répertoire de travail du runner est sur la VM. Le job échoue tout de suite, avec un message
   explicite, si le secret est vide.
3. Écriture d'un inventaire Ansible d'une ligne, `localhost` en connexion locale.
4. Premier passage du playbook, `--skip-tags deploy,runner` : comptes, Docker, pare-feu,
   arborescence, dépôt à jour, fichier d'environnement.
5. Authentification à GHCR **sous le compte de service**, puisqu'une authentification vaut pour
   l'utilisateur qui la fait et que le compose tourne sous ce compte.
6. Second passage du playbook, `--tags deploy` : tirage des images et démarrage de la pile.
7. Nettoyage, même en cas d'échec : suppression du fichier d'environnement et déconnexion du
   registre.

**Pourquoi deux passages.** Au tout premier déploiement, la machine n'a pas encore Docker. Il est
donc impossible de s'authentifier au registre avant que le playbook l'ait installé.

**Authentification au registre.** Les paquets GHCR sont privés et il n'existe aucun jeton personnel.
Le job déclare `packages: read` et utilise le `GITHUB_TOKEN` de son exécution, qui expire à la fin
du job. Rien de durable ne reste sur la machine.

## Tests et couverture

`backend-test` exige un vrai PostgreSQL, pas un double. Le service `postgres:16` du job est piloté
par des secrets de dépôt, et `conftest.py` valide l'URL de test, recrée une base dédiée suffixée
`_test`, joue les migrations Alembic puis insère le jeu de données de test. La base est supprimée en
fin de session.

Les rapports de couverture sont publiés en artefacts, `backend-coverage` pour `coverage.xml` et
`web-coverage` pour `lcov.info`. Le détail des suites est dans `tests-et-qualite.md`.

## Reproduire la chaîne en local

```bash
# backend
cd services/backend
ruff check . && ruff format --check .
pytest --cov=app --cov-report=term-missing

# front
cd services/web
npm ci
npm run lint && npm run typecheck && npm run typecheck:test
npm run test:coverage

# images et rapports Trivy (Docker, Trivy et jq requis)
cd ../..
docker build -f services/backend/Dockerfile -t seo-backend:local .
docker build -t seo-web:local services/web
docker build -f services/ml/Dockerfile -t seo-mlflow:local .
for i in backend web mlflow; do
  trivy image --scanners vuln --pkg-types os,library --severity HIGH,CRITICAL \
    --format json --output "$i.json" "seo-$i:local"
done
```

Le pre-commit couvre déjà une partie de `backend-lint` avant même le commit, voir
`tests-et-qualite.md`.

## Ce qui n'est pas dans la chaîne

Écrit ici plutôt que passé sous silence.

- **Pas de seuil minimal de couverture.** La couverture est mesurée et publiée à chaque exécution,
  mais aucune valeur plancher ne fait échouer un job.
- **Pas d'analyse statique de qualité** type SonarQube. Ruff et ESLint couvrent le style, les
  erreurs courantes et une partie de la sécurité, pas la complexité ni la duplication.
- **Pas de détection de secrets dans l'historique.** Le pre-commit refuse une clé privée, ce qui ne
  couvre pas un jeton ou un mot de passe.
- **Pas de tests de bout en bout ni de test de charge.**
- **Pas de mise à jour automatisée des dépendances.** Les versions sont bornées à la main et les
  images sont rescannées à chaque fusion.
- **Le déploiement ne vérifie pas son effet.** Il enchaîne ses étapes et s'arrête à la première qui
  échoue, mais rien ne compare à la fin l'empreinte de l'image en service avec le commit déployé.
  C'est le contrôle qui aurait détecté une dérive silencieuse entre la configuration et les images.
