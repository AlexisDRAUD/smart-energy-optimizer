# Architecture

Documentation technique, livrable EC05. Ce document dit ce que fait chaque brique, pourquoi elle
existe et où elle s'arrête.

Le schéma est disponible sous trois formes : [`architecture.png`](architecture.png) pour le lire ou
l'insérer dans un document, [`architecture.svg`](architecture.svg) pour l'agrandir sans perte, et
[`architecture.mmd`](architecture.mmd), la source Mermaid qui fait foi et se modifie en une ligne.
Les deux rendus se régénèrent avec `mmdc -i docs/architecture.mmd -o docs/architecture.svg`.

## Le principe

Une chaîne à sens unique. Chaque étage lit l'étage précédent et n'écrit que le sien. Aucun étage ne
modifie ce qu'il a lu. C'est ce qui rend toute la chaîne rejouable.

```
API source  ->  bronze  ->  silver  ->  gold  ->  API  ->  dashboard
```

## Les briques

Neuf conteneurs, décrits dans `docker-compose.yml`. Cinq d'entre eux partagent la même image
backend avec des commandes différentes : l'API, le collecteur, l'ETL, le worker de prévision et le
superviseur. Ils partagent le code et la cadence de livraison, mais restent dans des conteneurs
séparés, parce qu'un collecteur qui plante ne doit pas emporter le dashboard.

| Conteneur | Rôle | Cadence |
|---|---|---|
| `db` | PostgreSQL 16, toutes les tables | permanent |
| `migrate` | migrations Alembic, comptes, reprise d'historique, puis s'arrête | une fois au démarrage |
| `api` | API REST, authentification, agrégats | permanent |
| `web` | nginx, sert le front et relaie `/api/` | permanent |
| `collector` | interroge l'API source, écrit le brut | 60 s |
| `etl` | transforme le brut en couche validée | 60 s |
| `model` | charge le modèle et écrit les prévisions | 60 s |
| `supervisor` | surveille l'erreur du modèle et décide | 300 s |
| `mlflow` | serveur de suivi et registre de modèles | permanent |
| `minio` | stockage objet des artefacts de modèles | permanent |

L'ordre de démarrage est contraint : `migrate` doit se terminer avec succès avant que l'API, le
collecteur, l'ETL, le worker et le superviseur ne démarrent. Sans cette condition, plusieurs
conteneurs joueraient les migrations en parallèle.

## Les étages de données

### Bronze, le brut

`raw_readings` porte la réponse de la source telle quelle, en JSONB. Rien n'y est interprété : ce
qui est jeté à cet étage est perdu pour toujours, alors que ce qui est gardé peut être retravaillé.
`site_id` et `measured_at` en sont extraits par des colonnes générées, ce qui permet une clé unique
sans dupliquer la donnée. La table est en insertion seule, l'insertion étant idempotente.

`raw_snapshots` porte les référentiels, sites, état des capteurs et alertes de la source, sans clé
unique : c'est un historique de ce qui a été reçu, pas un état courant.

### Silver, le validé

`readings` est la version propre et typée des mesures, avec la valeur brute conservée à côté de la
valeur éventuellement réparée, l'indicateur d'imputation et la méthode employée. `sites` est le
référentiel courant, `sensor_status` l'historique de l'état des capteurs.

### Gold, l'exploitable

`data_quality_daily` résume la qualité par site et par jour. `predictions` porte les prévisions et
leur notation. `alerts` porte les alertes remontées par la source, avec leur acquittement local.

### Transverse

`etl_runs` trace chaque passage de l'ETL avec sa fenêtre, ce qu'il a lu, écrit, réparé, et son
statut. C'est cette table qui porte l'avancement et qui sert de borne au passage suivant.

Le détail des colonnes et des contraintes est dans `data-contract.md`.

## La collecte

Le collecteur fait un passage toutes les soixante secondes : les trois référentiels, puis la mesure
courante de chaque site. Il n'interprète rien et ne meurt jamais. Une source injoignable est
journalisée et retentée au tour suivant, un site injoignable est ignoré pour ce passage sans priver
les autres.

Sa fenêtre est l'instant présent, il ne rattrape rien. C'est le seul maillon où une panne perd des
données définitivement.

La reprise d'historique est un mode séparé du même collecteur, lancé une seule fois au premier
démarrage, par fenêtres de mille minutes, avec écriture au fil de l'eau après chaque fenêtre et
trois tentatives par fenêtre. Sa garde de reprise mesure la **couverture** de l'historique et non la
simple présence de lignes : passer de sept jours à deux ans redéclenche donc la reprise au lieu de
sauter les sites déjà remplis plus court.

## La transformation

L'ETL avance par fenêtre de **réception**, pas de mesure. Chaque passage repart de la borne haute de
son dernier passage réussi, moins deux minutes de recouvrement, et lit tout ce qui est arrivé depuis.

Trois propriétés en découlent, et ce sont elles qui font la robustesse de l'ensemble.

Rien n'est écrit sur le brut pour marquer ce qui a été traité, donc la table brute reste en
insertion seule et l'ETL reste rejouable à volonté. Relire une mesure déjà chargée ne produit rien,
la clé unique absorbe le doublon : la justesse ne dépend pas de la fenêtre, seule la quantité de
travail en dépend. Et un passage en échec ne fait pas avancer la borne, donc son travail est repris
au passage suivant sans intervention.

Ordre d'un passage : référentiel des sites, historique des capteurs, alertes de la source,
transformation des mesures par lots de mille, recalcul des profils d'imputation, réparation des
valeurs manquantes, puis résumé de qualité et trace du passage.

Deux détails valent d'être connus. L'historique des capteurs traite **tous** les instantanés de la
fenêtre et pas seulement le dernier, sinon ceux arrivés entre deux passages seraient perdus. Et les
journées dont la qualité est recalculée se déduisent de la date des **mesures**, pas de la fenêtre,
parce qu'une reprise d'historique écrit aujourd'hui des mesures vieilles de deux ans.

## La prévision

Un modèle par site, pas un modèle global. L'entraînement et le service partagent le même paquet
`packages/features`, ce qui ferme par construction le décalage entre les variables apprises et les
variables servies.

Le worker de prévision charge le modèle du site depuis le registre MLflow par son alias
`production`, calcule la prévision à deux heures depuis les derniers relevés, et l'écrit. À chaque
passage il note aussi les prévisions arrivées à échéance en y attachant la mesure réelle ; l'erreur
absolue est une colonne générée par la base.

**S'il ne trouve pas de modèle, il n'écrit rien.** Il n'existe aucun repli statistique dans ce
chemin : une prévision affichée vient d'un modèle, ou n'existe pas.

Le même passage transforme une prévision en **alerte d'anticipation**. Si la consommation prévue
monte plus vite qu'un seuil exprimé en pourcentage par heure, une alerte de type `forecast` est
ouverte, de sévérité croissante selon le dépassement. C'est le seul endroit du projet où le backend
produit une alerte à partir d'une règle qui lui est propre, et c'est ce qui donne au modèle un
usage concret : signaler une montée de charge **avant** qu'elle ne soit constatée.

Le superviseur lit la table des prévisions, calcule l'erreur glissante par site, va chercher son
seuil dans MLflow, et décide. Il journalise sa décision et **ne déclenche aucun réentraînement** :
une dérive lève une alerte, elle ne remplace pas un modèle toute seule.

Le détail est dans `ml.md`.

## L'exposition

L'API expose les référentiels, les mesures agrégées, la qualité, les alertes, les prévisions et la
performance du modèle. Les chiffres du dashboard, consommation totale et taux de charge, sont
calculés à la volée à partir du dernier relevé valide de chaque site : aucune table d'agrégat
pré-calculée n'existe, et un site sans relevé exploitable est signalé plutôt que compté à zéro.

L'authentification est par jeton JWT, avec trois rôles appliqués route par route. Le détail est dans
`api-contract.md` et dans `rapport-securite.md`.

Le front est une application React servie par nginx, qui relaie `/api/` vers l'API par le réseau
interne de Docker. Le navigateur ne parle donc qu'au port 80. Le détail des écrans est dans
`interface.md`.

## Choix d'architecture

**Une seule base pour les trois étages.** Sept sites à la minute représentent de l'ordre du
gigaoctet sur deux ans. PostgreSQL sur une machine tient cette charge sans difficulté, et le patron
médaillon apporte ici la séparation des responsabilités et la rejouabilité, pas la mise à l'échelle.
Les paliers suivants, dans l'ordre, seraient le partitionnement par temps ou TimescaleDB, puis un
moteur en colonnes, puis seulement un traitement distribué.

**Le brut en JSONB plutôt qu'en colonnes.** Un champ ajouté par la source n'oblige à aucune
migration et n'est jamais perdu.

**Des boucles dans les processus plutôt qu'un ordonnanceur.** À une minute, une boucle interne suffit
et supprime une dépendance. Un ordonnanceur comme Airflow se justifierait avec plusieurs chaînes,
des dépendances entre elles et des reprises à gérer.

**Des conteneurs séparés partageant une image.** Un seul artefact construit, scanné et publié, mais
des cycles de vie indépendants.

## Ce que l'architecture ne fait pas

- **Aucune supervision technique** type Prometheus. La supervision est applicative, portée par
  `etl_runs`, `data_quality_daily`, l'état des capteurs et la notation des prévisions.
- **Aucune alerte sortante.** Les alertes sont affichées et acquittées, rien n'est envoyé.
- **Aucune détection d'anomalie sur les mesures réelles.** Les alertes de mesure viennent de la
  source, le backend n'y applique aucun seuil. Il ne calcule que l'alerte d'anticipation, sur la
  prévision.
- **Aucune file de messages** entre la collecte et la transformation. La base joue ce rôle, ce qui
  tient tant qu'il n'y a qu'un consommateur.
