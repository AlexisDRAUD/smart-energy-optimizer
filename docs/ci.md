# Chaine d'integration

Le fichier unique `.github/workflows/ci.yml` decrit toute la chaine. Il tourne sur
`push` et `pull_request` vers `main` et `dev`. Aucune etape ne se declenche
ailleurs : une branche de travail ne consomme des minutes qu'au moment de la
demande de fusion.

Deux versions d'outils sont figees en haut du fichier et valent pour tous les
jobs : `PYTHON_VERSION` (3.12) et `NODE_VERSION` (20). Elles doivent suivre les
images des `Dockerfile`, sinon la chaine valide un code qui ne tournera pas en
production.

## Les jobs

| Job | Depend de | Ce qu'il fait | Ou |
|---|---|---|---|
| `backend-lint` | rien | `ruff check .` puis `ruff format --check .` sur **tout le depot** | racine |
| `backend-test` | `backend-lint` | `pytest` avec couverture, contre un vrai PostgreSQL | `services/backend` |
| `web-lint` | rien | `npm run lint` (eslint) puis `npm run typecheck` (`tsc --noEmit`) | `services/web` |
| `web-test` | `web-lint` | `npm run typecheck:test` puis Jest avec couverture | `services/web` |

Les deux domaines avancent en parallele. A l'interieur d'un domaine, les tests
attendent le lint : inutile de reserver un PostgreSQL ou de reinstaller les
dependances npm pour un code que le linter refuse deja.

```
backend-lint ──> backend-test
web-lint     ──> web-test
```

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

Ils sont joints au run, pas commites. On les recupere depuis la page du run pour
la soutenance ou pour un outil de couverture.

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
```

Le pre-commit (`ruff`, fins de fichier, cle privee, marqueurs de conflit) couvre
deja une partie du `backend-lint` avant meme le commit ; voir `quality.md`.
