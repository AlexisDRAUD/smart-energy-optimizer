# Exploitation

L'usage au jour le jour et le diagnostic. Pour installer, voir `setup.md`. Pour les réglages,
`configuration.md`.

## Démarrer, arrêter, regarder

```bash
docker compose up -d
docker compose ps
docker compose logs -f collector
docker compose logs -f etl
docker compose down
```

Un collecteur en bonne santé écrit une ligne par minute :

```
INFO app.collector.loop: Passage: 7/7 site(s) lus, 7 mesure(s) inseree(s)
```

Un ETL en bonne santé aussi :

```
INFO app.etl.main: Passage termine: fenetre ... lues=21 ecrites=7 rejetees=0 reparees=1
```

`lues` est plus grand que `ecrites` : c'est normal, la fenêtre recouvre les deux minutes
précédentes et le rechargement d'une mesure déjà en base ne produit rien.

## Vérifier que la chaîne tourne

Les quatre compteurs, dans l'ordre du flux. Aucun ne doit rester à zéro.

```bash
docker compose exec db psql -U seo -d seo -c "
SELECT (SELECT count(*) FROM raw_readings) brut,
       (SELECT count(*) FROM readings)     mesures,
       (SELECT count(*) FROM sites)        sites,
       (SELECT count(*) FROM etl_runs)     passages"
```

| Ce qui est à zéro | Ce qu'il faut regarder |
|---|---|
| `brut` | le collecteur : source injoignable, mauvaise `SOURCE_API_BASE_URL` |
| `mesures` mais `brut` non nul | l'ETL : `docker compose logs etl` |
| `sites` | aucun instantané `api_sites` n'est arrivé, donc le collecteur ne tourne pas |
| `passages` | l'ETL n'a pas fini un seul passage |

Les derniers passages de l'ETL, avec leur coût :

```bash
docker compose exec db psql -U seo -d seo -c "
SELECT id, status, rows_read, rows_written, rows_imputed,
       round(extract(epoch FROM finished_at - started_at)::numeric, 1) AS duree_s
FROM etl_runs ORDER BY id DESC LIMIT 10"
```

Un passage en régime normal lit une vingtaine de lignes et dure moins d'une seconde. Un passage
qui lit des dizaines de milliers de lignes à chaque tour signale un `ETL_WINDOW_OVERLAP_MINUTES`
trop large.

Un passage en `failed` ne fait **pas** avancer la fenêtre : ce qu'il n'a pas traité est repris
au tour suivant, sans intervention. Son message d'erreur est dans `etl_runs.error_message`.

## Voir la base

```bash
docker compose exec db psql -U seo -d seo
```

| Commande | Ce qu'elle fait |
|---|---|
| `\dt` | liste les tables |
| `\d+ readings` | détaille une table, colonnes, contraintes et commentaires |
| `\q` | quitter |

Pour une seule requête, sans entrer dans psql :

```bash
docker compose exec db psql -U seo -d seo -c "SELECT count(*) FROM readings"
```

Avec un outil graphique, DBeaver ou l'onglet Database de PyCharm : hôte `localhost`, port
`5432` ou la valeur de `DB_HOST_PORT`, base `seo`, utilisateur `seo`, mot de passe du `.env`.
Le `127.0.0.1:` devant le port dans le compose limite l'accès à la machine hôte, ce qui ne gêne
pas un client local.

## Amorçage

Il est automatique. `migrate` reprend l'historique de tous les sites sur `BACKFILL_DAYS` jours
au premier démarrage, et **ne fait rien** si `raw_readings` contient déjà une ligne.

Pour le lancer à la main, par exemple sur un site précis ou avec une autre profondeur :

```bash
docker compose run --rm collector python -m app.collector.backfill --site SITE003 --days 2
```

Pour forcer une reprise alors que la base contient déjà des mesures :

```bash
docker compose run --rm collector python -m app.collector.backfill --force
```

**Ne pas relancer la reprise pour combler un trou.** L'endpoint historique régénère les données
à chaque appel : une deuxième reprise écrirait des valeurs différentes de celles déjà en base.
La clé unique empêche les doublons, elle n'empêche pas l'incohérence.

## Rejouer une fenêtre de transformation

Sans risque : la clé unique sur site et horodatage empêche les doublons, et le brut n'est
jamais modifié.

```bash
# un seul passage, la fenetre habituelle
docker compose run --rm etl python -m app.etl --once

# rejouer depuis une date, pour retransformer et reparer une periode
docker compose run --rm etl python -m app.etl --once --since 2026-09-01T00:00:00
```

`--since` élargit à la fois la fenêtre de lecture du brut et celle de réparation.

Pour reconstruire entièrement la couche transformée depuis le brut :

```bash
docker compose exec db psql -U seo -d seo -c "TRUNCATE readings"
docker compose run --rm etl python -m app.etl --once --since 1970-01-01T00:00:00
```

C'est la propriété qui justifie de garder le brut intact. Compter une trentaine de secondes
pour 70 000 lignes.

## Réparation des valeurs nulles

Combien de mesures sont réparées, et par quelle méthode :

```bash
docker compose exec db psql -U seo -d seo -c "
SELECT imputation_method, count(*) FROM readings WHERE is_imputed GROUP BY 1"
```

Les trous encore ouverts, qui touchent l'instant présent et ne sont **pas** comblés :

```bash
docker compose exec db psql -U seo -d seo -c "
SELECT site_id, measured_at, null_reasons FROM readings
WHERE consumption_kwh_raw IS NULL AND NOT is_imputed ORDER BY measured_at"
```

Quelques lignes datées des dernières minutes sont normales. Une accumulation signale que le
profil des sites est passé à `unknown` :

```bash
docker compose exec db psql -U seo -d seo -c "
SELECT site_id, imputation_profile, imputation_profile_at FROM sites ORDER BY site_id"
```

## Le port 5432 est déjà pris

```
Error response from daemon: Ports are not available:
exposing port TCP 127.0.0.1:5432 ... address already in use
```

Un autre PostgreSQL écoute déjà sur le poste. Trouver lequel :

```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
docker ps
```

Deux réponses possibles. Soit l'arrêter. Soit, plus simple, changer le port de ce projet dans
le `.env` :

```bash
DB_HOST_PORT=5433
```

Seul l'accès depuis la machine hôte change. Les conteneurs se joignent entre eux par le réseau
interne, sur 5432, et ne voient pas la différence.

## L'authentification échoue au bout d'une heure

Le jeton d'accès dure une heure et se renouvelle par le cookie de session. Si le renouvellement
échoue, vérifier `COOKIE_SECURE` : à `true` sans HTTPS, le navigateur n'envoie pas le cookie et
la session tombe sans message clair.

## Une modification n'a aucun effet

Deux causes, dans cet ordre :

```bash
docker compose up -d --build                        # l image n a pas ete reconstruite
docker compose up -d --force-recreate <service>     # le conteneur tourne encore sur l ancienne
```

`docker compose start` et `docker compose restart` relancent le conteneur **existant** : ils ne
prennent pas une image fraîchement construite.

## Sauvegarde

Le dépôt porte le code et les migrations. La base n'est pas sauvegardée, et elle n'a pas à
l'être : la couche brute se reconstruit par une nouvelle reprise, avec la réserve ci-dessus sur
la régénération des données, et la couche transformée se reconstruit entièrement depuis le brut.
