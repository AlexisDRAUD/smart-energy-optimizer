# Contrat de donnees

Ce fichier fait foi. Toute modification passe par une demande de fusion et prévient les
personnes qui tiennent le collecteur, l'ETL et l'API.

## Conventions générales

- Horodatages en **temps universel**, type `timestamptz`. Conversion en heure locale a
  l'affichage uniquement.
- Énergie en **kWh**, puissance en **kW**. L'unité figure dans le nom de la colonne.
- Identifiants de site **tels que la source les fournit**, sans reformatage.
- Une valeur nulle recue est une valeur nulle stockée. Elle n'est jamais supprimée.

## Couche brute

Table `raw_readings`.

| Colonne | Type | Note                                            |
|---|---|-------------------------------------------------|
| `id` | `bigserial` | clé technique                                   |
| `received_at` | `timestamptz` | horodatage de reception, pas celui de la mesure |
| `source` | `text` | `api_current`, `api_backfill`, `csv_import`     |
| `payload` | `jsonb` | la reponse telle quelle                         |

Règles. Insertion seulement. Le role applicatif n'a ni `UPDATE` ni `DELETE` sur cette table.
Partitionnement par mois.

## Couche transformée

Table `readings`.

| Colonne | Type | Note |
|---|---|---|
| `site_id` | `text` | |
| `measured_at` | `timestamptz` | horodatage de la mesure |
| `consumption_kwh` | `double precision` | valeur utilisee |
| `consumption_kwh_raw` | `double precision` | valeur d'origine, nulle si la source l'a envoyee nulle |
| `is_imputed` | `boolean` | |
| `imputation_method` | `text` | `interpolation`, `report`, nul si non impute |
| `temperature_celsius` | `double precision` | |
| `humidity_percent` | `double precision` | |
| `solar_irradiance_wm2` | `double precision` | |
| `quality` | `text` | niveau de qualite rapporte par la source |

Cle unique sur `(site_id, measured_at)`. C'est elle qui rend le job de transformation
rejouable sans créer de doublon.

Table `sites` : `site_id`, `site_type`, `site_name`. Les libelles ne sont pas répétés sur
chaque ligne de mesure.

## Ce qui n'est pas stocke

Les colonnes de calendrier présentes dans les CSV fournis (`hour`, `day_of_week`, `day_name`,
`month`, `is_weekend`, `is_working_hours`) ne sont pas stockées. Elles se recalculent depuis
`measured_at` par le paquet commun. Une colonne stockée qui se recalcule finit par contredire
l'horodatage a côté d'elle.

La colonne `consumption_euros` des CSV dépend d'un prix qui n'est pas dans le jeu de données.
Elle est conservée dans la couche brute et n'est utilisée ni pour le modèle ni pour les
recommandations, qui restent chiffrées en kWh.

## Sources

| Source              | Periode             | Pas | Usage |
|---------------------|---------------------|---|---|
| CSV fournis         | 2023 et 2024        | 1 min | amorcage, entrainement |
| Endpoint historique | jusqu'à aujourd'hui | 1 min | reprise unique |
| Endpoint instantané | temps réel          | 1 min | collecte permanente |

Point ouvert à régler avant l'amorçage : le raccord entre les CSV et l'API, memes noms de
colonnes, memes unites, memes identifiants de site, et que faire des périodes qui se
recouvrent.

## Trous de collecte

L'endpoint historique regénère les donnees a chaque appel, il ne peut donc pas servir a
combler un trou. Un trou reste un trou. Aucune ligne n'est écrite, et le dashboard affiche
un avertissement de donnees incompletes.

## Imputation

Ordre a respecter. Conserver le brut, réparer avant d'imputer.

- Moins de 3 mesures manquantes consécutives et profil variable : interpolation.
- Moins de 3 et profil stable : report de la dernière valeur connue.
- 3 ou plus : pas d'imputation, le trou reste visible.
- Jamais de moyenne mobile.
