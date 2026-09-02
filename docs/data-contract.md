# Contrat de donnees

Ce fichier fait foi. Toute modification passe par une demande de fusion et prévient les
personnes qui tiennent le collecteur, l'ETL et l'API.

Le contrat est organisé dans l'ordre du flux. Chaque étage dit ce qu'il lit, ce qu'il écrit,
et ce qu'il n'a pas le droit d'écrire. Personne n'écrit dans une table d'un autre étage.

## Le flux

```
source (API du formateur)
   |
   v  collector          ecrit  raw_readings, raw_snapshots
   |
   v  etl                ecrit  sites, readings, sensor_status, etl_runs, data_quality_daily
   |
   +--> ml               ne lit que readings et sites, n'ecrit rien en base
   |
   v  api                ecrit  users, predictions, alerts
   |
   v  web                n'ecrit rien, n'accede pas a la base
```

Une seule base PostgreSQL. Deux couches, brute et transformée. Le schema n'existe que dans
`db/migrations/`.

## Conventions générales

- Horodatages en **temps universel**, type `timestamptz`. Conversion en heure locale a
  l'affichage uniquement.
- Énergie en **kWh**, puissance en **kW**. L'unité figure dans le nom de la colonne.
- Identifiants de site **tels que la source les fournit**, sans reformatage.
- Les noms de colonnes reprennent les noms de la source quand ils existent. Un renommage
  au passage est une erreur de correspondance qui ne se voit qu'en production.
- Une valeur nulle recue est une valeur nulle stockée. Elle n'est jamais supprimée.
- Aucun service ne crée de table a la main. Une table qui n'est pas dans `db/migrations/`
  n'existe pas.

## Ce que la source envoie

Repris de la documentation de l'API mock, c'est notre point de départ et il ne se négocie pas.

Objet `EnergyReading`, rendu par `/api/v1/sites/{id}/current` et par `/api/v1/readings`.

| Champ | Type | Note |
|---|---|---|
| `timestamp` | datetime | horodatage de la mesure |
| `site_id` | string | |
| `site_type` | string | répété sur chaque mesure, il appartient au site |
| `consumption_kw` | float ou nul | puissance instantanée |
| `consumption_kwh` | float ou nul | énergie sur la période |
| `voltage_v` | float ou nul | |
| `current_a` | float ou nul | |
| `power_factor` | float ou nul | |
| `temperature_celsius` | float ou nul | |
| `humidity_percent` | float ou nul | |
| `null_reasons` | tableau de chaines | pourquoi les champs sont nuls |
| `data_quality` | string | `good`, `partial`, `degraded`, `critical` |

Objet site, rendu par `/api/v1/sites` : `site_id`, `site_type`, `site_name`, `location`,
`capacity_kw`, `status`.

État des capteurs, rendu par `/api/v1/sensors/status` : pour chaque site, cinq capteurs
(`consumption`, `electrical`, `temperature`, `humidity`, `network`), chacun avec un `status`
et un `failing_until`, plus un `overall`.

## Etage 1. Collecteur

Lit la source. Écrit le brut, tel quel, sans rien interpréter. Ce qui est jeté ici est perdu
définitivement.

### `raw_readings`

Les mesures. Volumineuse, partitionnée par mois.

| Colonne | Type | Note |
|---|---|---|
| `id` | `bigserial` | clé technique |
| `received_at` | `timestamptz` | horodatage de reception, pas celui de la mesure |
| `source` | `text` | `api_current`, `api_backfill`, `csv_import` |
| `payload` | `jsonb` | la réponse telle quelle |

Insertion seulement. Le role applicatif n'a ni `UPDATE` ni `DELETE` sur cette table, par les
droits et pas par convention.

### `raw_snapshots`

Le référentiel et l'état des capteurs. Petite, non partitionnée, relue souvent.

| Colonne | Type | Note |
|---|---|---|
| `id` | `bigserial` | clé technique |
| `received_at` | `timestamptz` | |
| `source` | `text` | `api_sites`, `api_sensors` |
| `payload` | `jsonb` | la réponse telle quelle |

Deux tables brutes et non une seule, parce que ces lignes n'ont ni le meme volume ni la meme
durée de vie utile. Mélangées, les partitions mensuelles des mesures se rempliraient de
référentiel relu toutes les minutes.

N'y va pas : la moindre transformation, un calcul, un filtrage des valeurs nulles.

## Etage 2. ETL

Lit le brut, contrôle, répare, écrit le transformé.

Passe **toutes les minutes**, sur une **fenêtre glissante de 30 minutes**. Chaque minute est
donc revue une trentaine de fois. C'est voulu : une mesure absente au moment d'une passe est
reprise a la suivante, et une valeur nulle est réparée des que la mesure d'après arrive. Le
job est rejouable sans créer de doublon grace aux clés uniques ci-dessous.

### `sites`

| Colonne | Type | Note |
|---|---|---|
| `site_id` | `text` | clé primaire |
| `site_type` | `text` | `office`, `factory`, `datacenter`, autres |
| `site_name` | `text` | |
| `location` | `text` | |
| `capacity_kw` | `double precision` | sans elle, pas de taux de charge |
| `status` | `text` | `active`, `inactive` |
| `first_seen_at` | `timestamptz` | |
| `last_seen_at` | `timestamptz` | mis a jour a chaque passe |

Rempli par mise a jour ou insertion depuis `raw_snapshots`. Les libellés ne sont pas répétés
sur chaque ligne de mesure.

### `readings`

| Colonne | Type | Note |
|---|---|---|
| `site_id` | `text` | |
| `measured_at` | `timestamptz` | horodatage de la mesure |
| `consumption_kwh` | `double precision` | valeur utilisée, imputée ou non |
| `consumption_kwh_raw` | `double precision` | valeur d'origine, nulle si la source l'a envoyée nulle |
| `is_imputed` | `boolean` | |
| `imputation_method` | `text` | `interpolation`, `report`, nul si non imputé |
| `temperature_celsius` | `double precision` | |
| `humidity_percent` | `double precision` | |
| `data_quality` | `text` | `good`, `partial`, `degraded`, `critical` |
| `null_reasons` | `text[]` | tableau vide si rien ne manque, jamais nul |
| `ingested_at` | `timestamptz` | quand l'ETL a écrit la ligne |

Clé unique sur `(site_id, measured_at)`. C'est elle qui rend le job rejouable sans créer de
doublon.

`data_quality` et `null_reasons` sont contraints aux valeurs de la source. Une valeur inconnue
qui apparait est un changement de la source, elle doit faire échouer bruyamment plutot que
s'écrire en silence.

Pas de clé étrangère vers `sites`. Un site inconnu apparu dans la source ferait échouer le
job, alors que la règle du projet est que les contrôles de qualité marquent au lieu de bloquer.

### `sensor_status`

L'historique de santé des capteurs. Sans historisation, la page Qualité ne peut montrer que
l'instant présent, ce qui ne permet aucun diagnostic.

| Colonne | Type | Note |
|---|---|---|
| `site_id` | `text` | |
| `sensor` | `text` | `consumption`, `electrical`, `temperature`, `humidity`, `network` |
| `observed_at` | `timestamptz` | |
| `status` | `text` | `ok`, `failing` |
| `failing_until` | `timestamptz` | nul si le capteur va bien |

Clé unique sur `(site_id, sensor, observed_at)`.

### `etl_runs`

La trace des passes. C'est la source du bandeau "dernière synchro" du dashboard. Sans elle,
personne ne sait si l'absence de données vient d'un trou de collecte ou d'un ETL arreté.

| Colonne | Type | Note |
|---|---|---|
| `id` | `bigserial` | |
| `started_at` | `timestamptz` | |
| `finished_at` | `timestamptz` | nul tant que la passe tourne |
| `window_start` | `timestamptz` | fenêtre de brut traitée |
| `window_end` | `timestamptz` | |
| `rows_read` | `integer` | |
| `rows_written` | `integer` | |
| `rows_imputed` | `integer` | |
| `status` | `text` | `running`, `ok`, `partial`, `failed` |
| `error_message` | `text` | |

### `data_quality_daily`

Un résumé par site et par jour, écrit a la fin de chaque passe pour les jours touchés. Le
graphe du dashboard le lit directement, il ne rescanne pas des millions de lignes a chaque
affichage.

| Colonne | Type | Note |
|---|---|---|
| `site_id` | `text` | |
| `day` | `date` | jour en temps universel |
| `expected_points` | `integer` | 1440 pour une journée complète au pas d'une minute |
| `received_points` | `integer` | |
| `missing_points` | `integer` | attendus moins recus, c'est le trou de collecte |
| `null_points` | `integer` | recus mais sans valeur de consommation |
| `imputed_points` | `integer` | |
| `computed_at` | `timestamptz` | |

Clé unique sur `(site_id, day)`.

N'y va pas : le calcul des variables d'entrée du modèle, il est dans le paquet commun.

## Etage 3. Modele

Lit `readings` et `sites`. **N'écrit rien en base.** Il produit un artefact versionné dans
MLflow, pas des lignes. Le code qui sert les prédictions est dans l'API, c'est donc l'API qui
enregistre ce qui a été prédit.

Cible : consommation en kWh a **deux heures**. L'horizon vient du temps qu'il faut a un
exploitant pour reperer le risque, decider, prevenir et agir. La colonne `horizon_minutes` de
`predictions` existe quand meme, pour qu'ajouter un second horizon soit une ligne de
configuration et pas une migration.

Variables d'entrée : toutes calculées par `packages/common`, jamais ailleurs. Aucune n'est
stockée en base, elles se recalculent depuis `readings`.

## Etage 4. API

Le seul composant qui écrit les tables de service, et le seul que le front interroge.

### `users`

`/auth/login` et `/auth/me` sont au contrat d'API, il leur faut une table.

| Colonne | Type | Note |
|---|---|---|
| `id` | `bigserial` | |
| `email` | `text` | unique |
| `password_hash` | `text` | l'empreinte, jamais le mot de passe |
| `role` | `text` | `viewer`, `operator`, `admin` |
| `is_active` | `boolean` | |
| `created_at` | `timestamptz` | |

### `predictions`

Écrite par une boucle de fond de l'API, **toutes les minutes**, pour chaque site. Le front ne
déclenche rien : sinon il n'existerait de prédictions que quand quelqu'un regarde l'écran.

La boucle part de la dernière minute **disponible** dans `readings`, sans supposer qu'elle est
écrite. L'API et l'ETL passent tous les deux a la minute, ils se croisent. Cette dernière
minute peut aussi porter une valeur nulle pas encore imputée, puisqu'un trou ouvert reste
ouvert : le calcul des variables d'entrée doit encaisser une valeur manquante sans échouer. La colonne `actual_kwh` est remplie plus tard par
l'ETL, quand la mesure réelle arrive. C'est ce qui rend la surveillance possible : une
prédiction non conservée ne se compare a rien.

| Colonne | Type | Note |
|---|---|---|
| `id` | `bigserial` | |
| `site_id` | `text` | |
| `predicted_at` | `timestamptz` | moment de l'émission |
| `target_at` | `timestamptz` | instant prédit |
| `horizon_minutes` | `integer` | 120 aujourd'hui, soit deux heures |
| `model_name` | `text` | |
| `model_version` | `text` | version chargée par l'API au démarrage |
| `predicted_kwh` | `double precision` | |
| `actual_kwh` | `double precision` | nul tant que la mesure n'est pas arrivée, donc deux heures |
| `absolute_error` | `double precision` | calculé par la base, pas par un service |
| `scored_at` | `timestamptz` | |

Clé unique sur `(site_id, target_at, model_version, horizon_minutes)`. Un redémarrage de l'API
ne doit pas créer une seconde prédiction pour le meme instant.

### `alerts`

Émises par notre API, pas recopiées de la source. Les alertes de la source servent de
référence de comparaison, elles arrivent dans le brut.

| Colonne | Type | Note |
|---|---|---|
| `id` | `bigserial` | |
| `site_id` | `text` | |
| `detected_at` | `timestamptz` | |
| `type` | `text` | `spike`, `threshold`, `anomaly`, `outage`, `sensor` |
| `severity` | `text` | `low`, `medium`, `high`, `critical` |
| `message` | `text` | |
| `value` | `double precision` | la valeur qui a déclenché |
| `threshold_value` | `double precision` | le seuil franchi |
| `status` | `text` | `open`, `acknowledged`, `closed` |
| `acknowledged_at` | `timestamptz` | |
| `acknowledged_by` | `bigint` | vers `users.id` |

Clé unique sur `(site_id, type, detected_at)`. Sans statut, la liste ne fait que grandir et la
page Alertes devient illisible au bout d'une journée.

## Etage 5. Front

N'accède pas a la base et n'écrit rien. Son contrat, ce sont les objets JSON que l'API rend,
décrits dans `api-contract.md`. Les règles qui le concernent ici :

- Il recoit toujours les horodatages en temps universel au format ISO 8601 et convertit a
  l'affichage.
- Il ne calcule ni seuil, ni agrégat, ni taux de charge. L'API rend la valeur déja calculée.
- Une fenêtre sans donnée rend une liste vide et un indicateur de complétude, pas une erreur.
- Tout écran qui affiche des mesures affiche aussi leur complétude. Un graphe qui cache un
  trou de collecte ment.

## Ce qui n'est pas stocké dans la couche transformée

Tout ce qui suit reste dans le brut, en JSONB, et se ressort par une requête si le besoin
apparait.

- `voltage_v`, `current_a`, `power_factor`. Ce sont des mesures électriques, le produit porte
  sur la consommation. Elles seraient stockées "au cas ou" et personne ne les afficherait.
- `consumption_kw`. La source envoie la meme valeur que `consumption_kwh`. Stocker deux fois
  la meme chose sous deux unités produit une contradiction le jour ou la source les
  différencie.
- `site_type` sur chaque ligne de mesure. Il appartient au site, il est dans `sites`.
- Les colonnes de calendrier des CSV (`hour`, `day_of_week`, `day_name`, `month`,
  `is_weekend`, `is_working_hours`). Elles se recalculent depuis `measured_at` par le paquet
  commun. Une colonne stockée qui se recalcule finit par contredire l'horodatage a coté d'elle.
- `consumption_euros` des CSV. Elle dépend d'un prix absent du jeu de données. Les
  recommandations restent chiffrées en kWh.
- L'ensoleillement. Il est présent dans les CSV mais la source ne l'envoie jamais. Une
  variable qui existe a l'entrainement et disparait en production dégrade le modèle sans
  qu'aucun test n'échoue.

## Sources

| Source | Periode | Pas | Usage |
|---|---|---|---|
| CSV fournis | 2023 et 2024 | 1 min | amorcage, entrainement |
| Endpoint historique | jusqu'a aujourd'hui | 1 min | reprise unique |
| Endpoint instantané | temps réel | 1 min | collecte permanente |

Point ouvert a régler avant l'amorcage : le raccord entre les CSV et l'API, memes noms de
colonnes, memes unités, memes identifiants de site, et que faire des périodes qui se
recouvrent.

## Valeurs nulles et trous de collecte

Deux situations différentes qu'on appelle souvent du même mot. Elles ne se traitent pas pareil.

**Valeur nulle recue.** La source a répondu, avec un `consumption_kwh` nul, un `data_quality`
dégradé et un `null_reasons` qui dit pourquoi. La ligne existe en base, avec ses valeurs
nulles. C'est cette situation, et elle seule, qui s'impute.

**Trou de collecte.** Le collecteur était arrêté, la source n'a rien répondu, aucune ligne
n'existe. L'endpoint historique regénère les données a chaque appel, il ne peut donc pas
servir a combler un trou. Un trou reste un trou. Aucune ligne n'est écrite, il se lit dans
`data_quality_daily` et le dashboard affiche un avertissement de données incomplètes.

## Imputation

Conserver le brut, réparer avant d'imputer, tracer ce qui a été réparé.

### Ce qui s'impute

**La consommation seulement.** `consumption_kwh_raw` garde toujours ce que la source a envoyé,
`consumption_kwh` porte la valeur utilisée. `is_imputed` et `imputation_method` décrivent la
consommation, rien d'autre.

La météo n'est jamais imputée. Une température nulle reste nulle. Le modèle retenu est un
ensemble d'arbres renforcés par gradient, il gère les valeurs manquantes nativement, et un
flag d'imputation unique pour la ligne serait ambigu le jour ou seul le capteur de
température tombe alors que la consommation est bonne.

### Quand

Un trou n'est imputable que s'il est **refermé**, c'est a dire encadré par deux valeurs
réelles. Un trou encore ouvert, qui touche l'instant présent, a une valeur avant mais pas de
valeur après. L'imputer serait de l'extrapolation, pas de l'interpolation. Il reste nul, et
la passe suivante le traitera quand la mesure d'après sera arrivée.

Conséquence a assumer : une valeur nulle apparait d'abord telle quelle sur le dashboard, puis
se répare une minute plus tard. C'est le prix de ne rien inventer.

### Comment

Longueur du trou mesurée en **minutes**, une fois refermé. Un seuil en nombre de points
changerait de sens le jour ou le pas de mesure change.

| Trou refermé | Profil du site | Traitement |
|---|---|---|
| jusqu'a 3 minutes | variable | interpolation linéaire entre les deux valeurs réelles |
| jusqu'a 3 minutes | stable | report de la dernière valeur réelle connue |
| plus de 3 minutes | quel qu'il soit | pas d'imputation, le trou reste visible |

Jamais de moyenne mobile, elle lisse les pics réels, et les pics sont précisément ce que le
produit doit détecter.

### Idempotence

**L'imputation se calcule toujours depuis `consumption_kwh_raw`, jamais depuis
`consumption_kwh`.**

C'est la règle la plus importante de cette section. La fenêtre repasse une trentaine de fois
sur chaque minute. Une imputation calculée a partir d'une valeur déja imputée produirait, a la
passe suivante, une valeur inventée a partir d'une valeur inventée. La courbe dériverait en
quelques minutes sans qu'aucune erreur ne s'affiche.

En pratique la passe ne considère que les lignes ou `consumption_kwh_raw IS NULL`. Repasser
cent fois sur la même fenêtre donne exactement le même résultat.

### Ce qui peut être réécrit

Une ligne imputée peut être réécrite par une meilleure imputation, ou par la valeur réelle si
elle finit par arriver. Une valeur réelle n'est jamais écrasée, ni par une imputation, ni par
un nul.
