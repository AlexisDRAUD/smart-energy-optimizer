# Contrat d'API

La référence qui fait foi est la documentation OpenAPI générée par FastAPI, sur
`http://localhost:8080/docs`. Ce fichier en donne la carte et les règles.

Toutes les routes sont préfixées par `/api/v1`. Une modification incompatible crée `/api/v2`,
elle ne modifie pas `/api/v1` en place.

Les tables citées ici sont décrites dans `data-contract.md`, qui fait foi pour les colonnes.

## Authentification

| Route | Methode | Role |
|---|---|---|
| `/api/v1/auth/login` | POST | rend un jeton signe et ouvre la session |
| `/api/v1/auth/refresh` | POST | rend un jeton neuf a partir du cookie de session |
| `/api/v1/auth/logout` | POST | efface le cookie de session |
| `/api/v1/auth/me` | GET | identite du porteur du jeton |

Deux jetons, deux roles distincts.

L'**access token** se transmet dans l'entête `Authorization: Bearer <jeton>` a chaque appel.
Il vit une heure (`ACCESS_TOKEN_EXPIRE_MINUTES`). Le front le garde en memoire et dans le
`sessionStorage` de l'onglet.

Le **refresh token** ne sort jamais du cookie `enervision_refresh_token`, pose par `login`
et `refresh`. Il est `httpOnly`, donc invisible au JavaScript, limite au chemin
`/api/v1/auth`, donc jamais envoye aux autres routes, et `Secure` des que `COOKIE_SECURE`
est actif. Il vit sept jours (`REFRESH_TOKEN_EXPIRE_DAYS`) et sert uniquement a obtenir un
access token neuf.

Le cookie fonctionne parce que le navigateur ne parle qu'a une seule origine : le front et
l'API sont servis par le meme hote, Vite qui proxifie `/api` en local, nginx qui relaie
`location /api/` en production. Exposer l'API sur son propre domaine casserait ce montage
et imposerait `SameSite=None` et du CORS avec identifiants.

Quand un appel repond 401, le front appelle `refresh` une fois et rejoue l'appel. Si le
refresh echoue a son tour, la session est finie et l'utilisateur revient sur la page de
connexion.

Un jeton signe ne se revoque pas : `logout` efface le cookie du navigateur, mais un refresh
token copie ailleurs reste valable jusqu'a son expiration. Une revocation reelle demande une
table de sessions cote base, elle n'est pas faite.

Trois rôles, dans `users.role`. `viewer` lit tout. `operator` lit et acquitte les alertes.
`admin` ajoute la gestion des comptes. Une route qui modifie quelque chose annonce le rôle
qu'elle exige.

## Donnees

### Graphique de comparaison (valeurs natives)

`GET /api/v1/consumption-chart?site_id=...&start=...&end=...` est une route de
lecture authentifiée dédiée au dashboard. Les utilisateurs actifs peuvent lire tous
les sites, conformément à la politique actuelle ; un site inconnu rend 404. Il
n'existe pas actuellement de droits par site.

- `start` et `end` sont obligatoires, en ISO 8601 UTC. L'historique est exactement
  `[start, end[`, de durée strictement positive et au plus 30 jours (720 heures
  écoulées). `end` ne peut pas être dans le futur.
- Les prévisions après cette fenêtre sont séparées dans `future_predictions`, sur
  `[end, future_end[`, où `future_end = end + 120 minutes`. Pour une requête ancienne,
  ce sont des prévisions après sa borne de fin, pas nécessairement après aujourd'hui.
- Le MVP sélectionne exclusivement H+2 (`horizon_minutes=120`) et le nom/version
  configurés par `LOCAL_MODEL_NAME` / `LOCAL_MODEL_VERSION`, les mêmes paramètres
  que le producteur actuel. Aucun repli sur une autre version quand elle est absente.
  Le serveur renvoie ces métadonnées même si les séries sont vides.
- Plafonds fixes : 43 201 mesures et 43 321 prédictions (historique et futur réunis).
  Les requêtes filtrent par site et timestamps, utilisent les index composites
  existants, et lisent au plus plafond + 1 lignes pour détecter un dépassement.
  Chaque requête de séries a un délai SQL maximal de 5 secondes (local à la
  transaction) ; une expiration produit 503 explicite, sans réponse partielle.
  Les calculs utilisent la fenêtre complète ; dépassement de durée ou de volume =
  422 explicite. `limit`, `offset`, choix de modèle et autres paramètres supplémentaires
  sont refusés avec 422. Il n'y a pas de pagination sur cette route.
- `readings` contient les points natifs sélectionnés côté serveur par LTTB, sans somme,
  arrondi, conversion ou imputation supplémentaire. Les prédictions sont ordonnées par
  cible. Une minute absente ne devient pas une mesure nulle synthétique. Le plafond cible
  est de 600 points par série ; les nulls et les bornes de chaque segment sont obligatoires
  et peuvent faire dépasser ce nombre dans un cas très fragmenté.
- `downsampling` indique l'algorithme, le plafond cible et les nombres de points avant/après
  pour le réel, la prédiction historique et le futur. LTTB conserve les timestamps et valeurs
  des points choisis. Chaque valeur nulle, première/dernière valeur de la fenêtre et point de
  part et d'autre d'une rupture reste présent. `segment_start` marque le premier point de
  chaque portion continue : les intervalles créés par LTTB ne sont ainsi pas confondus avec
  les vrais trous de collecte. Aucun stockage n'est modifié.
- `reading_coverage`, `prediction_coverage` et `future_coverage` comptent les minutes
  UTC touchées par chaque fenêtre : attendues, reçues, absentes, reçues mais nulles,
  exploitables. `percent` est le pourcentage de minutes exploitables. Les bornes
  partielles comptent chacune une minute ; plusieurs observations dans une minute
  ne gonflent pas cette couverture. `first_at`/`last_at` décrivent les observations
  disponibles, y compris nulles, et ne remplacent jamais le domaine du graphique.
- `last_evaluated` est la dernière paire exploitable **dans l'historique demandé**,
  au même site et exactement `measured_at == target_at`, pour la version/H+2
  sélectionnés. Elle est évaluée à la lecture depuis le réel natif disponible,
  sans modifier les scores stockés. Le pourcentage conserve la formule d'affichage
  `(réel - prédit) / prédit * 100` ; il est nul si le prédit vaut zéro. Sans paire,
  l'objet est nul. La carte s'appelle « Dernier écart évalué » et indique date,
  horizon et version ; il ne s'agit pas d'un écart actuel.

Le graphique historique conserve toujours les bornes demandées. Le futur est dans
un graphique distinct. Les lignes sont interrompues sur une valeur nulle ou un
intervalle entre observations supérieur à la cadence attendue (60 secondes).
Un point isolé est dessiné ; aucune ligne ne relie artificiellement réel et prédit.
Les endpoints existants `/readings`, `/predictions` et `/model/performance`, leurs
sommes, paginations et calculs restent inchangés.

### Sites

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/sites` | GET | le référentiel, une entrée par site |
| `/api/v1/sites/{site_id}` | GET | un site |
| `/api/v1/sites/{site_id}/latest` | GET | la dernière mesure connue du site |

Un site rend `site_id`, `site_type`, `site_name`, `location`, `capacity_kw`, `status`,
`last_seen_at`. Ce sont les colonnes de `sites`, sans transformation.

`latest` rend la dernière ligne de `readings`, avec son `measured_at`, son `data_quality`,
son `is_imputed` et son âge en secondes. L'âge est calculé par l'API : le front n'a pas a
soustraire deux horodatages pour savoir si la donnée est fraiche.

### Mesures

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/readings` | GET | une série temporelle |

Paramètres : `site_id` (obligatoire), `start`, `end`, `granularity`, `limit`, `offset`.

`granularity` vaut `minute`, `quarter`, `hour` ou `day`. **L'agrégation est faite par l'API**,
jamais par le front. Un mois au pas de la minute fait quarante mille points par site, le
navigateur ne doit pas les recevoir pour en dessiner deux cents.

La réponse porte toujours deux parties, les points et un bloc de complétude :

```json
{
  "site_id": "SITE001",
  "granularity": "hour",
  "points": [
    {
      "measured_at": "2026-09-02T08:00:00Z",
      "consumption_kwh": 87.34,
      "is_imputed": false,
      "data_quality": "good"
    }
  ],
  "completeness": {
    "expected_points": 60,
    "received_points": 58,
    "imputed_points": 2,
    "missing_points": 2,
    "percent": 96.7
  }
}
```

Sur un point agrégé, `is_imputed` est vrai si au moins une mesure de l'intervalle l'était, et
`data_quality` prend le niveau le plus dégradé de l'intervalle. Une agrégation qui rendrait
`good` en moyennant du `critical` masquerait exactement ce que le produit doit montrer.

### Vue d'ensemble

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/overview` | GET | l'état instantané du parc |

Rend le nombre de sites, la consommation totale en kW, la capacité totale, le taux de charge
moyen, et la même chose par site. Les sites sans mesure valide sont **exclus du total et
comptés a part**, avec un indicateur de données incomplètes. Un total qui ignore
silencieusement trois sites en panne est un total faux.

Le taux de charge est calculé ici, a partir de `capacity_kw`. Le front ne divise rien.

### Qualite des donnees

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/quality` | GET | complétude par site et par jour |
| `/api/v1/quality/sensors` | GET | dernier état connu de chaque capteur ayant remonté |

`quality` lit `data_quality_daily` et prend `site_id`, `start`, `end`. C'est ce qui alimente
le graphe de la page Qualité, sans rescanner `readings`.

`sensors` lit `sensor_status` et rend, par site, la dernière observation de chaque capteur
qui a déjà remonté quelque chose. Un capteur qui n'a jamais rien envoyé n'apparait pas :
l'absence d'observation n'est pas une panne, et l'API ne parcourt pas une liste de capteurs
écrite dans le code pour les déclarer en défaut. `overall` vaut `failing` si au moins un
capteur observé est en défaut, `ok` si tous vont bien, et **null** quand le site n'a aucune
observation, parce que son état est alors inconnu.

### Etat du systeme

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/status` | GET | de quoi remplir le bandeau du dashboard |

Rend l'état de la source, l'horodatage de la dernière collecte réussie, celui de la dernière
passe d'ETL terminée et son résultat, lus dans `etl_runs`. C'est la route du bandeau
"API IoT, dernière synchro" de la maquette.

Elle est distincte de `/health`, qui sert aux sondes du conteneur et ne parle pas de la source.

## Predictions

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/predictions/latest` | GET | la dernière prédiction émise pour un site |
| `/api/v1/predictions` | GET | l'historique des prédictions, avec le réel et l'écart |
| `/api/v1/model` | GET | la version du modèle en service |
| `/api/v1/model/performance` | GET | l'erreur du modèle et celle des deux références |

Horizon **deux heures**, prédictions émises **a la minute** par une boucle de fond de l'API.
Le front ne déclenche jamais une prédiction, il lit ce qui a été émis.

Une prédiction rend `site_id`, `predicted_at`, `target_at`, `horizon_minutes`,
`predicted_kwh`, `model_version`, puis `actual_kwh` et `absolute_error`. Les deux derniers
sont nuls tant que la mesure réelle n'est pas arrivée, donc pendant deux heures. **Nuls, pas
absents** : une clé qui disparait oblige le front a tester son existence a chaque affichage.

`/model` décrit le modèle en service **a partir de la table `predictions`**, et rien d'autre :
`model_name`, `model_version` et `horizon_minutes` sont ceux de la dernière prévision écrite,
`last_prediction_at` sa date, `predictions_total` et `predictions_scored` les comptes. Tant
qu'aucune prévision n'existe, les trois premiers champs sont nuls.

Il n'y a ni date d'entrainement, ni métriques d'essai, ni indicateur MLflow dans cette
réponse : ce dépôt ne contient aucun entrainement et aucun client MLflow, ces champs
décrivaient donc quelque chose qui n'existe pas. Ils reviendront le jour ou un registre de
modeles sera branché.

`/model/performance` prend `site_id` et une période, et rend l'erreur absolue moyenne et
l'erreur quadratique moyenne du modèle, de la persistance et de la régression linéaire, sur
la même période. Les trois côte a côte, sinon le chiffre du modèle ne veut rien dire.

## Alertes

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/alerts` | GET | les alertes filtrées |
| `/api/v1/alerts/summary` | GET | les compteurs et la répartition par jour |
| `/api/v1/alerts/{id}/acknowledge` | POST | acquitte une alerte, rôle `operator` |

`alerts` prend `site_id`, `severity`, `status`, `type`, `start`, `end`, `limit`, `offset`. Par
défaut, les alertes ouvertes des sept derniers jours, les plus récentes d'abord.

Une alerte rend `id`, `site_id`, `detected_at`, `type`, `severity`, `message`, `value`,
`threshold_value`, `status`, `origin`, `acknowledged_at`. `origin` vaut `source` lorsque
l'alerte a été collectée puis matérialisée par l'ETL, et `internal` pour une règle interne
dont le producteur n'est pas qualifié plus précisément par le contrat actuel. Le frontend
affiche cette dernière comme « Règle interne — non attribuée au ML » : aucune alerte ne doit
être présentée comme issue d'un modèle ML validé sans provenance et version explicites.
Les valeurs et seuils restent ceux de l'émetteur ; le front ne les recalcule pas.

`summary` rend les compteurs par sévérité et la répartition par jour sur la période demandée.
C'est ce qui alimente les trois compteurs et le graphe de la maquette Alertes, en un appel
plutot qu'en comptant côté front une liste paginée.

`acknowledge` passe `status` a `acknowledged`, écrit `acknowledged_at` et l'identifiant du
porteur du jeton. Il n'y a pas de route qui supprime une alerte. Une alerte traitée reste,
c'est la trace.

Il n'y a plus de route `recommendations`. Elle rendait deux phrases en anglais écrites dans
le code, choisies par un seuil de 0,8 sur le taux de charge, avec des taux d'économie de 0,1
et 0,05 sortis de nulle part. Aucune table ne porte de recommandations et aucune règle métier
n'a été décidée. La route reviendra quand ce sera le cas, chiffrée **en kWh** et jamais en
euros, le prix n'étant pas dans le jeu de données.

Les alertes de la source sont exposées après validation et matérialisation par l'ETL. La copie
brute reste la trace rejouable du collector ; elle n'est jamais envoyée au frontend.

## Règles

- Les horodatages entrants et sortants sont en temps universel, au format ISO 8601.
- Une fenêtre sans donnée rend une liste vide et un indicateur de complétude, pas une erreur.
- Un champ sans valeur est rendu **nul**, il n'est jamais omis de la réponse.
- Toute réponse qui contient une série de mesures contient aussi sa complétude.
- Les erreurs suivent un format unique : `{"error": {"code": "...", "message": "..."}}`.
- Toute liste est paginée par `limit` et `offset`, avec un `total` dans la réponse.
- Le front ne calcule aucun seuil, aucun agrégat, aucun taux de charge, aucune moyenne.
  L'API rend la valeur déja calculée.
- Toute modification d'un schema exposé passe par une demande de fusion et prévient la
  personne qui tient le front.

## Codes

| Code | Quand |
|---|---|
| 200 | succès |
| 201 | création |
| 400 | requête mal formée |
| 401 | jeton absent, invalide ou expiré |
| 403 | jeton valide, rôle insuffisant |
| 404 | ressource inexistante |
| 422 | paramètre invalide, date illisible, `limit` hors plage |

Une période sans mesure n'est pas un 404. La ressource existe, elle est vide.

## Sante

`/health` rend l'état du service, l'accès a la base et la version du modèle chargée.
Cette route n'est pas préfixée par la version.
