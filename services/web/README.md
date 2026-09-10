# Front

Dashboard React, construit par Vite, servi en production par nginx qui relaie `/api/` vers l'API par
le réseau interne de Docker.

Les écrans et les indicateurs sont décrits dans [`interface.md`](../../docs/interface.md). Le contrat
d'API est dans [`api-contract.md`](../../docs/api-contract.md).

## Développer

```bash
cd services/web
npm ci
npm run dev
```

Le serveur de développement relaie `/api` vers le backend, ce qui garde une origine unique et fait
donc fonctionner le cookie de session comme en production.

## Contrôles

```bash
npm run lint            # eslint
npm run typecheck       # tsc --noEmit
npm run typecheck:test  # typage des tests
npm run test:coverage   # jest
```

## Structure

```
src/api/         client HTTP, renouvellement du jeton
src/components/  composants d affichage
src/hooks/       rafraichissement automatique, etats de chargement
src/pages/       un fichier par ecran
src/router/      declaration des routes
src/utils/       decoupage des series du graphique
tests/           tests de rendu et de comportement
```

## Deux règles à respecter

**Aucune donnée inventée.** Le front n'affiche que ce que l'API renvoie. Pas de valeur par défaut de
confort, pas de jeu de données fabriqué, pas de zéro à la place d'une mesure absente.

**`VITE_BACK_API_URL` est lue à la construction de l'image**, pas au démarrage du conteneur. Elle
reste vide tant que le front passe par le proxy nginx, ce qui rend la même image utilisable quelle
que soit l'adresse de la machine.
