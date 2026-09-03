# Installation

Comment obtenir, sur n'importe quel poste, exactement la meme base que les autres.

## Le principe

Personne ne cree de table a la main, et personne ne s'envoie de sauvegarde. Le schema n'existe
que dans `services/backend/alembic/versions/`, et c'est le depot qui le distribue.

Alembic est l'outil de migration. Il compare les modeles SQLAlchemy de
`services/backend/app/db/models/` a l'etat reel de la base, et applique les fichiers de
`versions/` qui manquent. Chaque base garde la liste de ce qu'elle a deja joue dans une table
`alembic_version`.

Dans `docker-compose.yml`, un service dedie applique tout cela une fois au demarrage :

```
db  ->  migrate  ->  api
```

`migrate` attend que PostgreSQL reponde, lance `alembic upgrade head`, insere les donnees de
demonstration, puis s'arrete. `api` ne demarre que si `migrate` s'est terminee sans erreur,
grace a `depends_on: condition: service_completed_successfully`.

`migrate` est une etape a part et pas un bout du demarrage de l'API, parce que le schema
appartient a la base et pas a un composant. Le jour ou le collecteur demarre en premier, il
trouve une base prete. Et en production, plusieurs copies de l'API qui demarrent en meme temps
ne se lancent pas toutes dans la migration en parallele.

C'est la meme image que l'API, avec une commande differente.

## Premiere installation

```bash
git clone <le depot>
cd smart-energy-optimizer

cp .env.example .env
```

Ouvrir `.env` et remplir les deux secrets, `POSTGRES_PASSWORD` et `JWT_SECRET_KEY` :

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Ces valeurs sont propres a chaque poste, elles ne se partagent pas et le fichier n'est jamais
commite.

Puis :

```bash
docker compose up
```

## Quand le schema change

Celui qui change le schema modifie un modele dans
`services/backend/app/db/models/`, puis genere la migration correspondante :

```bash
cd services/backend
DATABASE_URL=postgresql+psycopg://seo:<mot de passe>@127.0.0.1:5432/seo \
  python -m alembic revision --autogenerate -m "description du changement"
```

Le fichier genere se **relit toujours** avant d'etre commite. Alembic voit ce que les modeles
declarent, il ne devine ni une reprise de donnees ni un renommage : une colonne renommee se
presente comme une suppression suivie d'un ajout, et les valeurs sont perdues.

La migration part dans la meme demande de fusion que le modele et que `docs/data-contract.md`.

Les autres, apres avoir recupere la branche :

```bash
docker compose up --build
```

`migrate` applique la nouvelle migration sur la base existante, sans la detruire. C'est toute
la difference avec ce que faisait le projet avant : plus besoin de recreer la base a chaque
changement de schema.

## Repartir de zero

Reste possible et reste sans gravite, la base n'est pas la source de verite.

```bash
docker compose down -v && docker compose up
```

Le `-v` supprime le volume, donc les donnees. Elles se reconstruisent par l'amorcage, voir
`runbook.md`.

**A faire une fois** en recuperant cette branche : les volumes crees avant Alembic portent les
tables sans la table `alembic_version`, Alembic ne sait pas quoi en faire. Un `down -v` remet
tout d'aplomb.

## Travailler sans Docker

Les tests du backend et la generation de migrations tournent en local :

```bash
python -m venv .venv
.venv/bin/pip install -e packages/features
.venv/bin/pip install -r services/backend/requirements.txt
```

## Sur Azure

La production tourne sur Azure Container Apps avec un PostgreSQL manage, decision 35. La base
managee n'a pas de dossier `/docker-entrypoint-initdb.d`, mais ce n'est plus un probleme :
c'est la meme image `migrate` que celle du compose, lancee comme un job avant le deploiement de
l'API, avec `DATABASE_URL` pointant vers la base managee et `SEED_DEMO_DATA=0`.

| | En local | Sur Azure |
|---|---|---|
| Qui applique le schema | le service `migrate` du compose | la meme image, lancee comme un job |
| Donnees de demonstration | `SEED_DEMO_DATA=1` | `SEED_DEMO_DATA=0` |
| D'ou viennent les secrets | le `.env` | la configuration de l'application et un coffre |
| Comment on joint la base | `localhost:5432`, limite a la machine | le serveur manage, en SSL obligatoire, depuis une adresse autorisee dans le pare-feu |

Plus de `DROP SCHEMA public CASCADE` avant chaque mise a jour : les migrations s'appliquent les
unes apres les autres, et une base qui porte des donnees qu'on ne sait pas regenerer ne bloque
plus le projet. C'etait la limite assumee de la decision 30, elle tombe.

## En cas de doute

```bash
docker compose down -v && docker compose up
```

C'est presque toujours la bonne reponse a "ca marche chez moi".
