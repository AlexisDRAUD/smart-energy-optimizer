# web

Dashboard React du projet, servi par Vite.

## Regle

Aucune logique metier ici. Pas de seuil, pas d'agregat, pas de regle. Le front affiche ce que
l'API rend. Une regle dupliquee dans le front finit par diverger, et elle n'est testee nulle part.

## Lancer

Depuis la racine du depot, avec le reste de la pile :

```bash
docker compose up -d web
```

En local sans conteneur :

```bash
cd services/web
npm ci
VITE_API_BASE_URL=http://localhost:8080/api/v1 npm run dev
```

Le dashboard repond sur `http://localhost:5173`.

## Organisation

| Fichier | Role |
|---|---|
| `src/main.jsx` | point d'entree, monte l'application |
| `src/App.jsx` | coquille du dashboard |
| `src/api.js` | **seul** endroit qui appelle le backend |
| `src/index.css` | styles globaux |

`src/api.js` est le seul fichier qui fait un `fetch`. Aucun composant n'appelle le backend
directement : quand le contrat d'API change, un seul fichier bouge, et l'entete
`Authorization` n'aura qu'un endroit ou etre ajoute.

## Adresse du backend

Elle vient de `VITE_API_BASE_URL`, jamais en dur. Le compose la fournit. En dehors du compose,
elle se met dans un `.env` a la racine du depot, qui n'est jamais commite.

## Version

React 19, Vite 8. Les versions sont figees dans `package.json` et `package-lock.json`.
Personne ne met a jour une dependance sans le dire a l'equipe.
