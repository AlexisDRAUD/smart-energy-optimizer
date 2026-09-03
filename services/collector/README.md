# collector

Interroge la source toutes les minutes et ecrit la reponse telle quelle dans la couche brute
(`raw_readings`, et a terme `raw_snapshots`). Aucune transformation : ce qui est jete ici est
perdu definitivement (voir `docs/data-contract.md`, etage 1).

## Prerequis

- Python 3.12+
- Les dependances du service : `pip install -r requirements.txt`
- La base du projet demarree (`docker compose up -d db` a la racine du depot)
- L'API source joignable (adresse fournie par le formateur)

## Configuration

Le collecteur lit tout dans les variables d'environnement — aucune valeur en dur.
Les noms sont ceux du `.env.example` a la racine du depot :

| Variable | Role | Defaut dans le code |
|---|---|---|
| `SOURCE_API_BASE_URL` | adresse de l'API source | `http://127.0.0.1:8000` |
| `POSTGRES_HOST` | hote de la base | `localhost` |
| `POSTGRES_PORT` | port de la base | `5432` |
| `POSTGRES_USER` | utilisateur | `seo` |
| `POSTGRES_PASSWORD` | mot de passe | **aucun — obligatoire** |
| `POSTGRES_DB` | nom de la base | `seo` |

`POSTGRES_PASSWORD` n'a volontairement pas de valeur par defaut : le service refuse de
demarrer si elle est absente, plutot que d'echouer plus tard ou d'embarquer un secret.
Le defaut de `SOURCE_API_BASE_URL` pointe un serveur local : sans configuration explicite,
le collecteur ne tape jamais un environnement reel par accident.

### Fournir les variables en dev (PyCharm/IntelliJ)

1. `Run → Edit Configurations` → selectionner la configuration du collector
2. Champ **Environment variables** → ajouter :
   - `POSTGRES_PASSWORD=<le mot de passe du .env>`
   - `SOURCE_API_BASE_URL=<adresse fournie par le formateur>`
3. OK, relancer

En conteneur, le compose injecte ces variables depuis le `.env` : rien a faire.

## Lancer

Depuis `services/collector/src` :

    python -m collector

Le collecteur boucle indefiniment (une passe par minute en cible). Arret : Ctrl+C.

## Tests

Depuis `services/collector` :

    pytest

Les tests d'integration ecrivent dans la vraie base : ils exigent la base demarree et
`POSTGRES_PASSWORD` dans l'environnement de la config de test.

## Cas particulier : base sur une VM distante

Si la base tourne sur une VM (pas de Docker local), un tunnel SSH ramene son port en local :

    ssh -L 5432:localhost:5432 apprenant@<IP_DE_LA_VM>

La fenetre reste ouverte pendant le travail ; la configuration ci-dessus fonctionne alors
sans changement (`POSTGRES_HOST=localhost`).
