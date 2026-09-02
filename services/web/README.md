# EnerVision Frontend

Interface web React du tableau de bord EnerVision. Elle permet à un utilisateur authentifié de consulter les consommations énergétiques, les prévisions, les alertes et la qualité des relevés fournis par l’API FastAPI.

## Objectif

Le frontend ne génère ni ne modifie les données de démonstration. Il les récupère depuis l’API sécurisée, les présente par site et conserve la distinction entre :

- une mesure réelle ;
- une mesure incomplète ou imputée ;
- une prédiction persistée.

Cette séparation permet de tracer l’origine de chaque valeur affichée et d’éviter de présenter une prédiction comme une mesure IoT.

## Démarrage local

Prérequis : Node.js 20+ et l’API EnerVision démarrée sur `http://localhost:8000`.

```bash
npm install
cp .env .env
npm run dev
```

Le frontend est disponible sur `http://localhost:5173`.

En développement, Vite redirige automatiquement les requêtes commençant par `/api` vers `http://localhost:8000`. Cela évite un blocage CORS entre les deux serveurs.

### Configuration API

La variable `VITE_BACK_API_URL` définit le préfixe de l’API backend :

```dotenv
# API servie derrière le même domaine que le frontend
VITE_BACK_API_URL=

# Exemple d’API déployée sur un autre domaine
# VITE_BACK_API_URL=https://api.exemple.fr
```

L’API distante doit alors autoriser l’origine du frontend via CORS.

## Commandes

| Commande | Rôle |
| --- | --- |
| `npm run dev` | Démarre le serveur Vite de développement. |
| `npm run build` | Génère le bundle de production dans `dist/`. |
| `npm run preview` | Sert localement le bundle de production. |
| `npm run typecheck` | Vérifie les types TypeScript sans générer de fichiers. |

## Déploiement Docker

L’image compile le frontend avec Node.js, puis le sert avec Nginx sur le port `80`. Nginx transmet les appels `/api/*` au backend, ce qui permet au navigateur de communiquer avec l’API sans configurer CORS entre deux origines.

```bash
docker build -t enervision-front .
docker run --rm --publish 8080:80 \
  --env API_UPSTREAM=http://host.docker.internal:8000 \
  enervision-front
```

L’application est alors accessible sur `http://localhost:8080`.

`API_UPSTREAM` doit désigner l’URL interne du backend :

| Déploiement | Valeur `API_UPSTREAM` |
| --- | --- |
| API démarrée sur la machine hôte (macOS/Windows) | `http://host.docker.internal:8000` |
| Frontend et API dans le même réseau Docker, service API nommé `api` | `http://api:8000` |

L’image utilise `http://api:8000` par défaut. En production, définissez cette variable avec l’adresse du service backend déployé. Le build conserve `VITE_BACK_API_URL` vide afin que le client appelle le proxy Nginx relatif `/api`.

## Architecture

```text
src/
├── api/                    # Client HTTP et wrappers des endpoints FastAPI
├── components/
│   ├── charts/             # Composants SVG des graphiques
│   ├── common/             # Icônes, états de chargement et erreurs
│   ├── dashboard/          # Filtres partagés des tableaux de bord
│   └── settings/           # Modal de préférences utilisateur
├── context/
│   └── AuthProvider.tsx    # État de session JWT
├── hooks/                  # Chargement et sélection du site accessible
├── pages/                  # Une vue par route de l’application
├── router/routes.tsx       # Routes hash et navigation latérale
├── types/api.ts            # Contrats TypeScript des réponses API
├── utils/formatters.ts     # Formats de dates, énergie et qualité
├── App.tsx                 # Layout global, navigation et modal paramètres
└── main.tsx                # Point d’entrée React et fournisseur d’authentification
```

## Authentification

1. L’écran de connexion envoie l’identifiant et le mot de passe vers `POST /api/v1/auth/token`.
2. L’API renvoie un JWT.
3. Le token est conservé dans `sessionStorage`, uniquement pendant la session du navigateur.
4. Le client HTTP ajoute `Authorization: Bearer <token>` à chaque appel protégé.
5. La déconnexion efface le token et renvoie vers l’écran de connexion.

Les utilisateurs de démonstration et leurs mots de passe sont définis côté backend. Un utilisateur provisionné est limité au site qui lui est associé : le frontend affiche donc uniquement les données autorisées par l’API.

## Pages et données affichées

| Route | Vue | Endpoints utilisés |
| --- | --- | --- |
| `#/` | Vue d’ensemble | Sites, statistiques, dernier relevé, relevés, alertes et prochaine prédiction |
| `#/alertes` | Alertes | Sites et alertes actives ou résolues |
| `#/sites` | Sites | Sites et dernier relevé de chaque site autorisé |
| `#/modele-h2` | Modèle H+2 | Sites, dernier relevé et première prédiction future |
| `#/historique` | Historique | Sites et relevés persistés |
| `#/qualite-des-donnees` | Qualité des données | Relevés persistés et leurs indicateurs de qualité |
| `#/parametres` | Paramètres | Préférences locales de thème, langue et fuseau horaire |

Le routeur est basé sur le hash de l’URL. Les liens directs, ainsi que les boutons précédent et suivant du navigateur, restent donc fonctionnels sans configuration spécifique du serveur web.

## Graphique réel / prédiction

La vue d’ensemble récupère la liste complète des relevés du site avec `GET /api/v1/readings`.

- Les relevés dont `source !== "prediction"` forment la courbe réelle bleue.
- Les relevés dont `source === "prediction"` forment la courbe turquoise en pointillé.
- Le trait vertical **MAINTENANT** est placé sur le dernier relevé réel.
- L’axe temporel couvre les 24 heures de mesures minute par minute, suivies des 2 heures de prédictions persistées.

`GET /api/v1/sites/{site_id}/current` alimente les indicateurs « consommation actuelle » et ignore les points futurs. `GET /api/v1/predictions/sites/{site_id}/next` alimente l’indicateur de prochaine prédiction.

## Gestion des données incomplètes et prédites

Un relevé API contient toujours les colonnes suivantes :

| Champ | Utilisation frontend |
| --- | --- |
| `consumption_kwh_raw` | Mesure réelle ; pour une prédiction, valeur calculée à afficher. Peut être `null` pour une mesure dégradée. |
| `consumption_kwh_imputed` | Valeur imputée lorsque la mesure réelle est indisponible. |
| `data_quality` | Affiché comme qualité de donnée : `good`, `partial`, `degraded`, `critical` ou `predicted`. |
| `null_reasons` | Motifs qui expliquent une mesure réelle absente. |
| `source` | Distingue les relevés de l’ETL ou de l’API des prédictions (`prediction`). |

Le tableau Historique et la page Qualité des données affichent séparément la valeur brute et la valeur imputée. Aucun `null` n’est supprimé ou remplacé côté frontend.

## Préférences

La modal **Paramètres** propose :

- les thèmes clair, sombre, rose poudré, aurore, coucher de soleil et océan ;
- la langue utilisée pour les formats et l’attribut HTML de la page (les libellés sont actuellement en français) ;
- une liste de 38 fuseaux horaires avec l’heure locale actualisée ;
- la déconnexion de la session JWT.

Ces préférences sont actuellement conservées en mémoire pendant la session. Elles ne sont pas envoyées au backend, qui ne fournit pas d’endpoint de préférences utilisateur.

## Dépannage

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `401 Unauthorized` à la connexion | Compte inconnu, mot de passe incorrect ou token expiré | Utiliser un compte seedé ou provisionner le compte côté API. |
| Les appels API échouent depuis Vite | API FastAPI non démarrée | Vérifier `http://localhost:8000/health`. |
| Les appels échouent sur un environnement déployé | URL API ou politique CORS incorrecte | Définir `VITE_BACK_API_URL` et autoriser l’origine du frontend dans l’API. |
| Les prédictions n’apparaissent pas | Ancienne base de démonstration non réinitialisée | Appliquer la procédure de réinitialisation documentée dans le README du backend. |