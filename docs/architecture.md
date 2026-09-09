# Architecture

## Le flux

```
source (API du formateur)
   |
   v  collector    ecrit  raw_readings, raw_snapshots
   |
   v  etl          ecrit  sites, readings, sensor_status, alerts, etl_runs
   |
   +--> ml         ne lit que readings et sites, n ecrit rien
   |
   v  api          ecrit  users, predictions, alertes internes
   |
   v  web          n ecrit rien, n accede pas a la base
```

Chaque étage lit celui d'avant et n'écrit que ses propres tables. `data-contract.md` fait foi
sur le détail des colonnes et sur qui a le droit d'écrire quoi.

Le schéma d'ensemble est dans `architecture.mmd`, à coller sur https://mermaid.live.

## Composants

Trois images dans le compose. L'image `backend` est lancée cinq fois avec des commandes
différentes.

| Conteneur | Image | Rôle | Régime |
|---|---|---|---|
| `db` | postgres:16 | la base | permanent |
| `migrate` | backend | schéma, comptes, reprise d'historique | une fois, puis s'arrête |
| `collector` | backend | interroge la source, écrit le brut | permanent, 1 min |
| `etl` | backend | contrôle, répare, écrit le transformé | permanent, 1 min |
| `api` | backend | expose les données, prédit, alerte | permanent, boucle de prédiction 1 min |
| `supervisor` | backend | mesure l'erreur du modèle en production, décide des réentraînements | permanent, 5 min |
| `web` | web | dashboard nginx | permanent |
| `mlflow`, `minio`, `minio_setup` | ml, minio | registre des modèles et son stockage d'artefacts | voir `ml.md` |

Le superviseur ne lit que `predictions` et `sites`, n'écrit rien, et ne promeut jamais un
modèle. Ses règles et leurs raisons sont dans `ml-supervision.md`.

**Pourquoi une seule image pour le collecteur, l'ETL, l'API et le superviseur.** Ils partagent
la même base, les mêmes modèles et la même cadence de livraison. Ce sont quatre morceaux d'un
même programme, pas quatre services indépendants : quatre images auraient produit quatre jeux
de dépendances à maintenir sans rien apporter, puisqu'ils se déploient ensemble de toute façon.

Ils restent dans des conteneurs séparés, et c'est ce qui compte à l'exécution : le collecteur
qui plante ne doit pas emporter le dashboard, et chacun redémarre seul.

**Pourquoi le ML aura son image.** Dépendances lourdes qui ne servent qu'à lui, et cycle de vie
différent : il tournera à la demande, pas en continu. Il lit la base en SQL direct et n'y écrit
rien, donc il n'a pas besoin des modèles du backend.

## Cadence

Le collecteur et l'ETL portent leur cadence eux-mêmes, par une boucle qui dort entre deux
passages. Pas de cron, pas d'ordonnanceur. Un processus arrêté ne rattrape rien, ce qui est
cohérent avec notre position sur les trous de collecte.

Les deux passent à la minute. Un passage en échec est journalisé et oublié, la boucle continue.

### Ce que fait un passage du collecteur

1. lit `/api/v1/sites` et enregistre la réponse dans `raw_snapshots`, source `api_sites` ;
2. lit `/api/v1/sensors/status` et l'enregistre de même, source `api_sensors` ;
3. lit `/api/v1/alerts` et l'enregistre de même, source `api_alerts` ;
4. lit `/api/v1/sites/{id}/current` pour chaque site et écrit les mesures dans `raw_readings`,
   en une seule insertion par lot.

Un site injoignable est journalisé et sauté : les autres sont quand même collectés.

### Ce que fait un passage de l'ETL

1. met `sites` à jour depuis le dernier instantané `api_sites` ;
2. historise `sensor_status` depuis **tous** les instantanés `api_sensors` de sa fenêtre ;
3. valide et matérialise les alertes de **tous** les instantanés `api_alerts` de sa fenêtre ;
4. transforme les mesures brutes de sa fenêtre et les charge dans `readings` ;
5. répare les valeurs nulles refermées ;
6. recalcule `data_quality_daily` pour les jours qu'il vient de toucher ;
7. écrit sa trace dans `etl_runs`.

Le résumé quotidien vient en avant-dernier parce qu'il compte ce que les étapes précédentes
ont laissé en base. Sans lui, la page « Qualité des données » resterait vide alors que les
mesures sont bien là.

### Les deux fenêtres de l'ETL

Elles n'ont ni le même rôle ni la même largeur, et les confondre coûte cher.

**La fenêtre de lecture du brut** repart de la borne du dernier passage *réussi*, moins deux
minutes. Ce recouvrement n'existe que pour rattraper une ligne dont la transaction n'était pas
terminée au moment de la lecture. Une fenêtre large ne servirait à rien et coûterait cher :
après une reprise d'historique, les 70 000 lignes portent toutes le même horodatage de
réception, et trente minutes de fenêtre les reliraient entièrement à chaque passage, soit une
trentaine de secondes de travail pour écrire sept lignes.

Elle porte sur les deux tables brutes, mesures et instantanés. Ne lire que le dernier
instantané de capteurs perdrait définitivement ceux arrivés entre deux passes : `sensor_status`
est un historique, et il se trouerait dès que l'ETL prend du retard sur le collecteur, ce qu'un
simple arrêt suffit à produire. Chaque instantané est historisé sous son propre `received_at`,
donc rejouer une fenêtre redonne exactement le même historique.

**La fenêtre de réparation** fait trente minutes et porte sur `readings`, pas sur le brut.
C'est elle qui permet de réparer une valeur nulle une minute après le retour de la mesure.
Retransformer une ligne brute ne répare rien, elle redonnerait la même valeur nulle : la
réparation regarde les mesures voisines.

**L'avancement vit dans `etl_runs`**, la table de l'ETL. Rien n'est écrit sur le brut pour
marquer ce qui a été traité : cela obligerait l'ETL à écrire dans une table de l'étage 1, et
rejouer une période imposerait d'effacer la marque. Le brut reste en insertion seule et
rejouable autant de fois qu'on veut, ce qui est sa seule raison d'exister.

## Reprise d'historique

Au tout premier démarrage, `migrate` reprend l'historique de chaque site sur `BACKFILL_DAYS`
jours, par fenêtres de 1000 minutes et insertions par lot.

Elle saute les sites qui ont déjà leur historique. Ce n'est pas une protection contre les
doublons, dont la clé unique se charge, mais contre le **rejeu** : l'endpoint historique de la
source régénère ses données à chaque appel, reprendre un site déjà repris mélangerait deux
générations dans la même série.

**La garde est par site, pas globale.** Globale, un seul site repris suffisait à déclarer toute
la reprise faite : si la source refusait `SITE002` pendant que `SITE001` réussissait, `SITE002`
n'était plus jamais repris, et son historique manquait pour de bon.

Pour que cette garde soit exacte, la reprise d'un site est **tout ou rien** : ses fenêtres
sont toutes lues, puis écrites en un seul appel, donc dans une seule transaction. Un site dont
la source coupe à mi-parcours ne laisse aucune ligne, il ne peut donc pas passer pour repris.
Les appels réseau restent hors de la transaction, la tenir ouverte le temps d'une dizaine
d'allers-retours bloquerait le nettoyage de la table pour rien.

Le job **sort en erreur si au moins un site échoue**, sinon une reprise partielle passerait pour
une réussite dans le journal de démarrage. Rien n'est perdu pour autant : ces sites n'ont laissé
aucune ligne, le démarrage suivant les reprend sans intervention.

Cet échec est volontairement non bloquant pour la pile. `api`, `etl` et `collector` attendent que
`migrate` se termine *sans erreur*, et le script rattrape lui-même le code de retour de la
reprise : une source injoignable laisserait sinon toute la pile à l'arrêt, alors qu'un historique
manquant n'empêche ni la collecte ni le dashboard.

## Stockage

Un seul PostgreSQL, deux couches.

La **couche brute** en JSONB, insertion seulement, non partitionnée. PostgreSQL exige qu'une
clé unique porte la colonne de partitionnement : partitionner ferait sauter la déduplication
sur `(site_id, measured_at)`, dont dépendent le rejeu du collecteur et celui de la reprise.

La **couche transformée** en tables typées, avec une clé unique sur site et horodatage qui rend
l'ETL rejouable. `measured_at` y est ramené à la minute, les deux endpoints de la source ne
rendant pas la même forme d'horodatage.

Le schéma n'existe que dans `services/backend/alembic/versions/`, appliqué par Alembic.
Personne ne crée de table à la main.

## Exposition

Le compose ne publie que deux ports sur la machine hôte : l'API et le dashboard. La base est
limitée à `127.0.0.1`. Le front joint l'API par le réseau interne des conteneurs, à travers le
proxy nginx qui relaie `location /api/`. Voir `security.md`.

## Structure du dépôt

À quoi sert chaque dossier, et surtout ce qui n'a pas à y aller.

### `packages/features/`

Le calcul des variables d'entrée du modèle, écrit une seule fois, importé à la fois par
l'entraînement et par le service. Si les deux calculaient la même variable de deux façons, le
modèle se dégraderait en production sans qu'aucun test n'échoue.

C'est sa seule raison d'être, et c'est le seul paquet partagé du dépôt.
**N'y va pas** : tout le reste. Ce dont un seul composant se sert reste chez lui.

### `services/backend/`

Le collecteur, l'ETL, l'API et le superviseur. Seul composant qui touche à la base, et il en
porte le schéma.

| Dossier | Rôle | N'y va pas |
|---|---|---|
| `app/collector/` | interroge la source, écrit la réponse **telle quelle**. Contient la reprise d'historique | la moindre transformation : ce qui est jeté ici est perdu définitivement |
| `app/etl/` | lit le brut, contrôle, répare, écrit le transformé | le calcul des variables du modèle, il est dans `packages/features` |
| `app/supervisor/` | mesure l'erreur du modèle en production, décide et demande les réentraînements (`ml-supervision.md`) | la promotion d'un modèle : c'est le script d'entraînement qui compare et promeut |
| `app/api/`, `app/crud/`, `app/schemas/`, `app/services/` | le backend HTTP | l'accès direct à la base depuis l'extérieur |
| `app/analysis/` | analyses hors ligne, comme le backtest d'imputation | tout ce qui écrit en base |
| `app/db/` | modèles SQLAlchemy, session, comptes de démonstration | |
| `alembic/` | les migrations. **Le schéma n'existe que là** | |

**N'y va pas** : le code d'entraînement, il est dans `services/ml` et n'a pas les mêmes
dépendances.

### `services/ml/`

Entraînement, évaluation, publication dans MLflow. Produit un artefact versionné, pas un
service. **Pas terminé, hors de ce lot.**
**N'y va pas** : le code qui sert les prédictions, il est dans le backend.

### `services/web/`

Le dashboard React, servi par nginx. Affiche et filtre.
**N'y va pas** : la logique métier. Aucun seuil, aucun agrégat, aucune règle. Une règle
dupliquée dans le front finit par diverger, et elle n'est testée nulle part.

### `infra/`

L'infrastructure décrite en code.
**N'y va pas** : un secret, même temporaire.

### `data/`

Les CSV fournis par le formateur, en local uniquement. Le dossier est exclu du dépôt. Le dépôt
est public, aucune donnée ne s'y trouve.

### `.github/workflows/`

La chaîne d'intégration, décrite dans `ci.md`.
**N'y va pas** : un secret en clair.

### `docs/`

Toute la documentation. Les contrats de données et d'API font foi, le reste explique et
justifie.
