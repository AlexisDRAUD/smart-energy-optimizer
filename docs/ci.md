# Chaine d'integration

Le fichier unique `.github/workflows/ci.yml` decrit toute la chaine. Il tourne sur
`push` et `pull_request` vers `main` et `dev`. Aucune etape ne se declenche
ailleurs : une branche de travail ne consomme des minutes qu'au moment de la
demande de fusion.

Deux versions d'outils sont figees en haut du fichier pour les jobs de qualite :
`PYTHON_VERSION` (3.12) et `NODE_VERSION` (24). Les images Docker gardent leurs
propres versions de base dans chaque `Dockerfile` et sont validees separement par
Trivy.

## Les jobs

| Job | Depend de | Ce qu'il fait | Ou |
|---|---|---|---|
| `backend-lint` | rien | `ruff check .` puis `ruff format --check .` sur **tout le depot** | racine |
| `backend-test` | `backend-lint` | `pytest` avec couverture, contre un vrai PostgreSQL | `services/backend` |
| `web-lint` | rien | `npm run lint` (eslint) puis `npm run typecheck` (`tsc --noEmit`) | `services/web` |
| `web-test` | `web-lint` | `npm run typecheck:test` puis Jest avec couverture | `services/web` |
| `docker-security` | `backend-test`, `web-test` | construit et scanne les images backend et web avec Trivy | runner Docker |
| `docker-publish` | `docker-security` | publie dans GHCR les images deja scannees, uniquement sur un push vers `dev` | GHCR |

Les deux domaines avancent en parallele. A l'interieur d'un domaine, les tests
attendent le lint : inutile de reserver un PostgreSQL ou de reinstaller les
dependances npm pour un code que le linter refuse deja.

```
backend-lint ──> backend-test
                            ├──> docker-security ──> docker-publish (`dev` seulement)
web-lint     ──> web-test
```

## Images Docker et Trivy

`docker-security` s'execute pour les pull requests vers `main` ou `dev`, ainsi
que pour les push vers `dev`. Il construit localement les images backend et web,
puis Trivy analyse leurs paquets systeme et leurs bibliotheques. Le job ne recoit
que la permission `contents: read` et ne se connecte a aucun registre.

Le scan est limite aux severites `HIGH` et `CRITICAL`. Les deux niveaux sont
affiches dans les logs et dans le resume du job. La presence d'une vulnerabilite
`HIGH` est informative ; une ou plusieurs vulnerabilites `CRITICAL` font echouer
le job. Les vulnerabilites sans correctif disponible restent prises en compte.

Sur un push vers `dev`, les images qui ont passe ce controle sont exportees dans
un artefact intermediaire conserve un jour. `docker-publish` recharge exactement
ces images, obtient seul la permission `packages: write`, se connecte a GHCR,
puis publie les tags immuable `<sha>` et mutable `dev`. Une image refusee par la
politique Trivy ne peut donc pas etre publiee.

L'action Trivy est figee par son empreinte de commit, avec le commentaire de
version `v0.36.0`. Aucun resultat SARIF n'est envoye a GitHub Code Scanning : le
pipeline ne depend ainsi ni de la permission `security-events: write`, ni de
l'activation de cette fonctionnalite sur le depot.

## backend-test et la base

La suite exige un vrai PostgreSQL, pas un double : `conftest.py` recree une base
de test, joue les migrations Alembic puis insere le jeu de donnees de test. Le
job lance donc un service `postgres:16` a cote du runner.

Les identifiants viennent des **secrets de depot**, pas du fichier : il faut que
`POSTGRES_USER`, `POSTGRES_PASSWORD` et `POSTGRES_DB` soient definis dans les
reglages du depot GitHub. Le test se connecte a
`…@127.0.0.1:5432/<POSTGRES_DB>_test` via la variable `TEST_DATABASE_URL`.

Le contexte `secrets` n'est pas autorise dans le champ `options` d'un service :
la sonde de sante est un `pg_isready` sans argument, qui suffit a savoir que le
serveur accepte les connexions.

## web-test et le typage

Le `tsconfig.json` du front ne couvre que `src`. Les tests ont leur propre
`tsconfig.test.json` (types `jest` inclus), verifie a part par
`npm run typecheck:test`. Jest ne fait pas de controle de types : sans cette
etape, une erreur de typage dans un test passerait la chaine.

Jest transforme le TypeScript avec `babel-jest` et une config babel inline, pour
ne pas heriter du babel qu'utilise Vite au build. Voir les commentaires de
`services/web/jest.config.cjs`.

## Artefacts

| Artefact | Contenu | Produit par |
|---|---|---|
| `backend-coverage` | `services/backend/coverage.xml` (Cobertura) | `backend-test` |
| `web-coverage` | `services/web/coverage/lcov.info` | `web-test` |
| `trivy-image-reports-<sha>` | rapports JSON `backend.json` et `web.json`, conserves 30 jours | `docker-security` |
| `scanned-docker-images-<sha>` | images validees a transmettre au job de publication, conservees 1 jour | `docker-security` sur `dev` |

Ils sont joints au run, pas commites. On les recupere depuis la page du run pour
la soutenance ou pour un outil de couverture. Pour consulter un rapport Trivy,
ouvrir le run GitHub Actions, descendre jusqu'a la section **Artifacts**, puis
telecharger `trivy-image-reports-<sha>`. Le resume `Trivy image scan` donne les
comptages sans telechargement.

## Cache

`setup-python` et `setup-node` gardent en cache le dossier de paquets, indexe sur
le fichier de verrouillage (`services/backend/requirements.txt`,
`services/web/package-lock.json`). Un `package-lock.json` non commite ou desynchronise
casse `npm ci` : les deux fichiers de manifeste se committent ensemble.

## Reproduire en local

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
trivy image --scanners vuln --pkg-types os,library --severity HIGH,CRITICAL \
  --format json --output backend.json seo-backend:local
trivy image --scanners vuln --pkg-types os,library --severity HIGH,CRITICAL \
  --format json --output web.json seo-web:local
```

Le pre-commit (`ruff`, fins de fichier, cle privee, marqueurs de conflit) couvre
deja une partie du `backend-lint` avant meme le commit ; voir `tests-et-qualite.md`.
