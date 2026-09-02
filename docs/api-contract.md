# Contrat d'API

La référence qui fait foi est la documentation OpenAPI générée par FastAPI, sur
`http://localhost:8080/docs`. Ce fichier en donne la carte et les règles.

Toutes les routes sont préfixées par `/api/v1`. Une modification incompatible crée `/api/v2`,
elle ne modifie pas `/api/v1` en place.

Les tables citées ici sont décrites dans `data-contract.md`, qui fait foi pour les colonnes.

## Authentification

| Route | Methode | Role |
|---|---|---|
| `/api/v1/auth/login` | POST | rend un jeton signe |
| `/api/v1/auth/me` | GET | identite du porteur du jeton |

Le jeton se transmet dans l'entête `Authorization: Bearer <jeton>`. Durée de vie courte,
un jeton signé ne se révoque pas.

Trois rôles, dans `users.role`. `viewer` lit tout. `operator` lit et acquitte les alertes.
`admin` ajoute la gestion des comptes. Une route qui modifie quelque chose annonce le rôle
qu'elle exige.

## Donnees

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
| `/api/v1/quality/sensors` | GET | dernier état connu des cinq capteurs par site |

`quality` lit `data_quality_daily` et prend `site_id`, `start`, `end`. C'est ce qui alimente
le graphe de la page Qualité, sans rescanner `readings`.

`sensors` lit `sensor_status` et rend, pour chaque site, l'état de `consumption`,
`electrical`, `temperature`, `humidity`, `network`, plus un `overall`.

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

`/model` rend `model_name`, `model_version`, la date d'entrainement, l'horizon et les
métriques de l'essai. Si MLflow ne répond pas, l'API rend la version de la copie locale
chargée au démarrage et le signale, elle ne rend pas une erreur.

`/model/performance` prend `site_id` et une période, et rend l'erreur absolue moyenne et
l'erreur quadratique moyenne du modèle, de la persistance et de la régression linéaire, sur
la même période. Les trois côte a côte, sinon le chiffre du modèle ne veut rien dire.

## Alertes et recommandations

| Route | Methode | Rend |
|---|---|---|
| `/api/v1/alerts` | GET | les alertes filtrées |
| `/api/v1/alerts/summary` | GET | les compteurs et la répartition par jour |
| `/api/v1/alerts/{id}/acknowledge` | POST | acquitte une alerte, rôle `operator` |
| `/api/v1/recommendations` | GET | les recommandations pour un site |

`alerts` prend `site_id`, `severity`, `status`, `type`, `start`, `end`, `limit`, `offset`. Par
défaut, les alertes ouvertes des sept derniers jours, les plus récentes d'abord.

Une alerte rend `id`, `site_id`, `detected_at`, `type`, `severity`, `message`, `value`,
`threshold_value`, `status`, `acknowledged_at`. Les seuils sont calculés par l'API et rendus
avec l'alerte : le front affiche "812 kW pour un seuil de 720", il ne le recalcule pas.

`summary` rend les compteurs par sévérité et la répartition par jour sur la période demandée.
C'est ce qui alimente les trois compteurs et le graphe de la maquette Alertes, en un appel
plutot qu'en comptant côté front une liste paginée.

`acknowledge` passe `status` a `acknowledged`, écrit `acknowledged_at` et l'identifiant du
porteur du jeton. Il n'y a pas de route qui supprime une alerte. Une alerte traitée reste,
c'est la trace.

`recommendations` rend des actions chiffrées **en kWh**, avec le site, l'action proposée et le
gain estimé. Jamais en euros : le prix n'est pas dans le jeu de données.

Les alertes de la source, elles, ne sont pas exposées. Elles arrivent dans la couche brute et
servent de point de comparaison, pas de contenu du produit.

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
