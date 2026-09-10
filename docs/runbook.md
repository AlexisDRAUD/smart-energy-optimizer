# Exploitation

L'usage au jour le jour et le diagnostic. Pour installer, voir `setup.md`. Pour les réglages,
`configuration.md`.

## Sur le poste ou sur la VM

Toutes les commandes de ce document s'utilisent des deux côtés. Sur la VM, elles se lancent
depuis `/opt/enervision`, en `root` ou sous le compte de service :

```bash
cd /opt/enervision
docker compose ps
sudo -u enervision docker compose logs -f etl
```

La différence à garder en tête : sur le poste, les images sont construites localement ; sur la
VM, elles sont tirées du registre et une modification de code n'y arrive que par un
déploiement.

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

Il est automatique. `migrate` reprend l'historique sur `BACKFILL_DAYS` jours des sites dont la
couverture est insuffisante. La garde mesure la **profondeur réellement atteinte** et non la
simple présence de lignes : un site déjà repris sur sept jours sera donc repris à nouveau si la
profondeur demandée passe à deux ans. Un site que la source a refusé n'a laissé aucune ligne, il
est repris tout seul au démarrage suivant, et le journal de `migrate` le nomme.

L'écriture se fait au fil de l'eau, fenêtre par fenêtre, avec trois tentatives par fenêtre et un
point d'avancement toutes les cinquante fenêtres. Une interruption ne perd donc que la fenêtre en
cours, et le journal dit où elle s'est arrêtée.

Pour le lancer à la main, par exemple sur un site précis ou avec une autre profondeur :

```bash
docker compose run --rm collector python -m app.collector.backfill --site SITE003 --days 2
```

Pour forcer la reprise d'un site qui a déjà son historique :

```bash
docker compose run --rm collector python -m app.collector.backfill --site SITE003 --force
```

**Ne pas forcer la reprise pour combler un trou.** L'endpoint historique régénère les données à
chaque appel : la clé unique garde les valeurs déjà en base et ne comble que les minutes
absentes, avec des valeurs d'une autre génération. La série mélange alors deux tirages. Elle
empêche les doublons, elle n'empêche pas l'incohérence.

`--force` ne sert donc qu'à un site dont on veut jeter puis refaire l'historique, pas à en
réparer un partiel.

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

## Le déploiement n'a pas pris

Symptôme typique : un conteneur en `Restarting` avec un module Python introuvable, ou une
fonctionnalité annoncée qui n'apparaît pas. La cause la plus fréquente est une image en retard
sur le code, la configuration ayant été mise à jour par le dépôt cloné pendant que les images
restaient celles du déploiement précédent.

Le diagnostic tient en deux commandes, grâce au label de révision porté par chaque image :

```bash
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
  ghcr.io/alexisdraud/smart-energy-optimizer-backend:main
sudo -u enervision git -C /opt/enervision rev-parse HEAD
```

Deux empreintes différentes, l'image est en retard. Le tirage forcé la remet à jour :

```bash
docker compose pull --policy always
docker compose up -d
```

Lire aussi la colonne `STATUS` de `docker compose ps` : `Up (healthy)` est sain, `Up` sans
mention signifie qu'aucun test de santé n'est défini, `Exited (0)` est normal pour `migrate` et
`minio_setup`, et `Restarting (n)` est une boucle d'échec avec `n` pour code de sortie.

## Le modèle

Aucun modèle n'est entraîné automatiquement en production, `ML_TRAIN_ON_START` valant `0`.

```bash
# entrainer tous les sites, ou un seul
docker compose exec mlflow python /app/main.py
docker compose exec mlflow python /app/main.py --site-id SITE001
```

Pour un entraînement long, le détacher de la session SSH :

```bash
nohup docker compose exec -T mlflow python /app/main.py \
  > /var/log/enervision-train.log 2>&1 &
tail -f /var/log/enervision-train.log
```

Vérifier ensuite que le service s'en sert. Le worker tourne toutes les soixante secondes et
n'écrit rien tant qu'il ne trouve pas de modèle :

```bash
docker compose exec -T db psql -U seo -d seo -c "
SELECT model_name, model_version, count(*), max(target_at)
FROM predictions GROUP BY 1,2 ORDER BY 1"
```

Les noms attendus sont de la forme `EnerVision_RF_Predictor_<site>`. Si la table reste vide alors
que l'entraînement a réussi, lire `docker compose logs model` : c'est soit l'alias `production`
qui n'a pas été posé, soit le magasin d'artefacts qui ne répond pas.

L'interface MLflow n'est pas exposée. Elle s'atteint par un tunnel :

```bash
ssh -L 5050:127.0.0.1:5000 root@10.138.200.30   # puis http://localhost:5050
```

Le superviseur ne fait que journaliser ses décisions, sa trace est dans
`docker compose logs supervisor`.

## Sauvegarde et restauration

Sur la VM, une tâche planifiée quotidienne produit un dump compressé avec rotation. Les deux
scripts sont installés par le playbook.

```bash
/usr/local/bin/enervision-backup-db          # sauvegarde immediate
ls -lh /var/backups/enervision/
/usr/local/bin/enervision-restore-db /var/backups/enervision/enervision-AAAAMMJJ-HHMMSS.sql.gz
```

La restauration demande confirmation, arrête les services applicatifs le temps de l'opération et
les relance. Rien ne restaure automatiquement au démarrage.

Deux limites à connaître. Les sauvegardes vivent sur le disque de la machine qu'elles protègent,
elles couvrent l'erreur humaine et la corruption, pas la perte de la VM : une copie hors machine
reste à faire à la main. Et la restauration n'a pas encore été éprouvée.

En dernier recours, la chaîne se reconstruit sans sauvegarde : la couche brute par une nouvelle
reprise d'historique, avec la réserve ci-dessus sur la régénération des données par la source, et
la couche transformée entièrement depuis le brut.

**`docker compose down -v` supprime les volumes, donc la base.** Rien ne restaure derrière, et le
redémarrage suivant repart d'une base vide qui rejouera la reprise d'historique complète.
