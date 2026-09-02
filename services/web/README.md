# EnerVision Frontend

Interface web React du tableau de bord EnerVision. Elle permet à un utilisateur authentifié de consulter les consommations énergétiques, les prévisions, les alertes et la qualité des relevés fournis par l’API FastAPI.

## Objectif

Le frontend ne génère ni ne modifie les données de démonstration. Il les récupère depuis l’API sécurisée, les présente par site et conserve la distinction entre :

- une mesure réelle ;
- une mesure incomplète ou imputée ;
- une prédiction persistée.

Cette séparation permet de tracer l’origine de chaque valeur affichée et d’éviter de présenter une prédiction comme une mesure IoT.

## Démarrage local

Prérequis : Node.js 20+ et l’API EnerVision démarrée sur `http://localhost:8080`.

```bash
npm install
cp .env.example .env
npm run dev
```

Le frontend est disponible sur `http://localhost:5173`.

En développement, Vite redirige automatiquement les requêtes commençant par `/api` vers `http://localhost:8080`. Cela évite un blocage CORS entre les deux serveurs.

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
docker run --rm --publish 8081:80 \
  --env API_UPSTREAM=http://host.docker.internal:8080 \
  enervision-front
```

L’application est alors accessible sur `http://localhost:8081`.

`API_UPSTREAM` doit désigner l’URL interne du backend :

| Déploiement | Valeur `API_UPSTREAM` |
| --- | --- |
| API démarrée sur la machine hôte (macOS/Windows) | `http://host.docker.internal:8080` |
| Frontend et API dans le même réseau Docker, service API nommé `api` | `http://api:8080` |

L’image utilise `http://api:8080` par défaut. En production, définissez cette variable avec l’adresse du service backend déployé. Le build conserve `VITE_BACK_API_URL` vide afin que le client appelle le proxy Nginx relatif `/api`.

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

1. L’écran de connexion envoie l’adresse e-mail et le mot de passe au format JSON vers `POST /api/v1/auth/login`.
2. L’API renvoie un JWT.
3. Le token est conservé dans `sessionStorage`, uniquement pendant la session du navigateur.
4. Le client HTTP ajoute `Authorization: Bearer <token>` à chaque appel protégé.
5. La déconnexion efface le token et renvoie vers l’écran de connexion.

Les utilisateurs de démonstration et leurs mots de passe sont définis côté backend. L’API applique les rôles `viewer`, `operator` et `admin`; le frontend affiche les données que le token autorise.

## Pages et données affichées

| Route | Vue | Endpoints utilisés |
| --- | --- | --- |
| `#/` | Vue d’ensemble | `/overview`, sites, dernier relevé, relevés, prévisions, alertes et recommandations |
| `#/alertes` | Alertes | Sites et alertes actives ou résolues |
| `#/sites` | Sites | Sites et dernier relevé de chaque site autorisé |
| `#/modele-h2` | Modèle H+2 | Sites, dernier relevé et dernière prévision |
| `#/historique` | Historique | Sites et relevés persistés |
| `#/qualite-des-donnees` | Qualité des données | Relevés persistés et leurs indicateurs de qualité |
| `#/parametres` | Paramètres | Préférences locales de thème, langue et fuseau horaire |

Le routeur est basé sur le hash de l’URL. Les liens directs, ainsi que les boutons précédent et suivant du navigateur, restent donc fonctionnels sans configuration spécifique du serveur web.

## Graphique réel / prédiction

La vue d’ensemble récupère les relevés réels du site avec `GET /api/v1/readings` et les prévisions avec `GET /api/v1/predictions`.

- Les points de `readings.points` forment la courbe réelle bleue.
- Les éléments de `predictions.items` forment la courbe turquoise en pointillé.
- Le trait vertical **MAINTENANT** est placé sur le dernier relevé réel.
- Le sélecteur permet d’afficher les dernières 24 heures, 7 jours ou 30 jours de mesures. Les prévisions disponibles prolongent la courbe.

`GET /api/v1/sites/{site_id}/latest` alimente l’indicateur « consommation actuelle ». `GET /api/v1/predictions/latest?site_id=...` alimente l’indicateur de prévision.

## Gestion des données incomplètes et prédites

Un relevé API contient toujours les colonnes suivantes :

| Champ | Utilisation frontend |
| --- | --- |
| `consumption_kwh` | Valeur de consommation réelle, éventuellement imputée. |
| `is_imputed` | Indique qu’une valeur est imputée plutôt que relevée directement. |
| `data_quality` | Affiché comme qualité de donnée : `good`, `partial`, `degraded` ou `critical`. |
| `predicted_kwh` | Valeur de prévision retournée par les endpoints `/predictions`. |
| `target_at` | Horodatage UTC auquel la prévision s’applique. |

Le frontend conserve les valeurs absentes et les données imputées sans les masquer. Les prévisions ne sont jamais mélangées aux relevés réels.

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
| Les appels API échouent depuis Vite | API FastAPI non démarrée | Vérifier `http://localhost:8080/health`. |
| Les appels échouent sur un environnement déployé | URL API ou politique CORS incorrecte | Définir `VITE_BACK_API_URL` et autoriser l’origine du frontend dans l’API. |
| Les prédictions n’apparaissent pas | Ancienne base de démonstration non réinitialisée | Appliquer la procédure de réinitialisation documentée dans le README du backend. |
