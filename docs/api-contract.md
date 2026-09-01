# Contrat d'API

La référence qui fait foi est la documentation OpenAPI générée par FastAPI, sur
`http://localhost:8080/docs`. Ce fichier en donne la carte et les règles.

Toutes les routes sont préfixées par `/api/v1`. Une modification incompatible crée `/api/v2`,
elle ne modifie pas `/api/v1` en place.

## Authentification

| Route | Methode | Role |
|---|---|---|
| `/api/v1/auth/login` | POST | rend un jeton signe |
| `/api/v1/auth/me` | GET | identite du porteur du jeton |

Le jeton se transmet dans l'entête `Authorization: Bearer <jeton>`. Durée de vie courte,
un jeton signé ne se révoque pas.

## Donnees

TODO: à complété

## Predictions

TODO: à complété

## Alertes et recommandations

TODO: à complété

## Règles

- Les horodatages entrants et sortants sont en temps universel, au format ISO 8601.
- Une fenêtre sans donnée rend une liste vide et un indicateur de complétude, pas une erreur.
- Les erreurs suivent un format unique : `{"error": {"code": "...", "message": "..."}}`.
- Le front ne calcule aucun seuil ni aucun agrégat, il affiche ce que l'API rend.
- Toute modification d'un schema exposé passe par une demande de fusion et prévient la
  personne qui tient le front.

## Sante

`/health` rend l'état du service, l'accès a la base et la version du modèle chargée.
Cette route n'est pas préfixée par la version.
