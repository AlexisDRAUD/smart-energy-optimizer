# Runbook

Ce fichier couvre l'exploitation au jour le jour. Pour installer le projet sur un poste neuf,
voir `setup.md`.

## Démarrer et arrêter

```bash
docker compose up -d
docker compose ps
docker compose logs -f collector
docker compose down
```

## Voir la base

En local, un `psql` dans le conteneur :

```bash
docker compose exec db psql -U seo -d seo
```

| Commande | Ce qu'elle fait |
|---|---|
| `\dt` | liste les tables |
| `\d+ readings` | detaille une table, colonnes, contraintes et commentaires |
| `\q` | quitter |

Pour une seule requete, sans entrer dans psql :

```bash
docker compose exec db psql -U seo -d seo -c "SELECT count(*) FROM readings"
```

Avec un outil graphique, DBeaver ou l'onglet Database de PyCharm : hote `localhost`, port
`5432` ou la valeur de `DB_HOST_PORT`, base `seo`, utilisateur `seo`, mot de passe du `.env`. Le `127.0.0.1:` devant le port
dans le compose limite l'acces a la machine hote, ce qui ne gene pas un client local.

Sur Azure, la meme chose avec le serveur manage, en SSL obligatoire et depuis une adresse
autorisee dans le pare-feu du serveur :

```bash
psql "host=<serveur>.postgres.database.azure.com user=<utilisateur> dbname=seo sslmode=require"
```

## Le port 5432 est deja pris

```
Error response from daemon: Ports are not available:
exposing port TCP 127.0.0.1:5432 ... address already in use
```

Un autre PostgreSQL ecoute deja sur le poste. Trouver lequel :

```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
docker ps
```

Deux reponses possibles. Soit l'arreter, `brew services stop postgresql@16` ou `docker stop`.
Soit, plus simple, laisser la place et changer le port de ce projet dans le `.env` :

```bash
DB_HOST_PORT=5433
```

Puis `docker compose up -d`. Seul l'acces depuis la machine hote change, avec psql ou un
client graphique. Les conteneurs se joignent entre eux par le reseau interne, sur 5432, et
ne voient pas la difference.

## Amorçage,à faire une seule fois

```bash
# 1. import des CSV fournis
TODO: A complété
# 2. reprise de l'historique depuis l'API, la profondeur est un choix documente
TODO: A complété
```

Ne pas relancer la reprise pour combler un trou. L'endpoint historique regénère les données
à chaque appel, une deuxième reprise écrirait des valeurs différentes de celles déjà en base.

## Rejouer une fenêtre de transformation

```bash
TODO: A complété
```

Sans risque, la cle unique sur site et horodatage empêche les doublons.

## Sauvegarde

Le depot porte le code et les migrations. La base de la VM n'est pas sauvegardée, et elle n'a
pas a l'être : la couche brute se reconstruit depuis les CSV et une nouvelle reprise, avec la
reserve ci-dessus sur la regeneration.
