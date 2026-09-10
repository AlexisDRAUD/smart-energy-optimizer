# Configuration

Toutes les variables du projet vivent dans un seul fichier d'environnement. `.env.example` est la
**référence exhaustive** : il liste chaque variable avec un commentaire et une valeur d'exemple.
Ce document explique le système, pas la liste, pour que les deux ne divergent pas.

## Un fichier, trois lecteurs

```bash
cp .env.example .env
```

Le même fichier est lu par trois choses différentes, et c'est la source de la plupart des surprises.

1. **docker compose**, pour toutes les substitutions `${...}` du `docker-compose.yml`.
2. **Le backend lancé hors docker**, pour Alembic et pytest.
3. **Vite**, au moment de la construction de l'image du front, pour les variables préfixées `VITE_`.

Une variable préfixée `VITE_` est lue **à la construction** de l'image, pas au démarrage du
conteneur. La changer demande donc de reconstruire l'image du front.

## Le piège à connaître

Une variable présente dans le fichier d'environnement n'atteint un conteneur **que si elle est
déclarée dans le bloc `environment` du service** correspondant dans `docker-compose.yml`.

Sans cette déclaration, compose l'utilise pour ses propres substitutions mais ne la transmet pas, et
le code tourne alors sur sa valeur par défaut interne. Rien ne le signale. Le symptôme est
déroutant : on change une valeur dans le fichier, on redémarre, et il ne se passe rien.

Le contrôle tient en quelques lignes, et il vaut la peine d'être joué après toute modification :

```bash
python3 - <<'PY'
import re, io
compose = io.open("docker-compose.yml", encoding="utf-8").read()
env = {m.group(1) for m in re.finditer(r'^([A-Z0-9_]+)=', io.open(".env", encoding="utf-8").read(), re.M)}
used = {m.group(1) for m in re.finditer(r'\$\{([A-Z0-9_]+)', compose)}
print("jamais lues par le compose :", sorted(env - used) or "aucune")
print("attendues et absentes      :", sorted(used - env) or "aucune")
PY
```

Deux variables ressortent de ce contrôle et c'est **normal** : `DATABASE_URL` et
`MLFLOW_TRACKING_URI`. Elles ne servent qu'au backend lancé **hors docker**, pour Alembic, pytest ou
un worker lancé à la main. Sous compose, les deux valeurs sont fixées directement dans le fichier,
vers les hôtes du réseau interne, et celles du fichier d'environnement sont ignorées.

## Obligatoire ou facultatif

Cinq variables sont **obligatoires** : le mot de passe PostgreSQL, la clé de signature des jetons,
le mot de passe des comptes de démonstration, et les deux identifiants du magasin d'objets. Elles
sont déclarées avec la syntaxe `${VAR:?message}`, donc la pile refuse de démarrer si l'une manque,
plutôt que de démarrer sur une valeur par défaut.

Ce choix vient d'un incident réel, décrit dans `rapport-securite.md` : des valeurs par défaut
publiées font démarrer une production sur des identifiants connus de tous.

Toutes les autres variables ont une valeur par défaut raisonnable dans le compose et peuvent être
omises.

## Les familles de variables

| Famille | Ce qu'elle règle |
|---|---|
| Images | registre, étiquette et politique de tirage. Voir `deploiement.md` |
| Base | compte, mot de passe, nom de base, port publié en local |
| Source | adresse de l'API de mesures |
| Collecteur | cadence d'interrogation, profondeur de la reprise d'historique |
| ETL | cadence, taille des lots, recouvrement de fenêtre |
| Imputation | fenêtre de réparation, âge de recalcul des profils |
| API et front | ports, interface d'écoute du dashboard, adresse d'API du front |
| Authentification | clé de signature, durées de vie des jetons, cookie sécurisé |
| Prévision et supervision | cadences des deux boucles, seuil et référence minimale de l'alerte d'anticipation, fenêtres et seuils du superviseur |
| MLflow et MinIO | adresse de suivi, ports locaux, identifiants du magasin, entraînement au démarrage |

## Local et production, deux fichiers distincts

Le fichier du poste et celui de la VM ne partagent aucun secret. Trois valeurs changent de sens
entre les deux :

| Variable | Poste | VM |
|---|---|---|
| `WEB_BIND` | `127.0.0.1`, le dashboard n'est joignable que localement | `0.0.0.0`, joignable depuis le réseau |
| `IMAGE_*` | vide, les images sont construites et taguées en local | registre, étiquette de branche, politique `missing` |
| `ML_TRAIN_ON_START` | `1`, pratique en développement | `0`, l'entraînement est déclenché explicitement |

`BACKFILL_DAYS` mérite une attention particulière : sa valeur au **tout premier démarrage** décide
de la profondeur d'historique reprise. La garde de reprise mesurant la couverture, l'augmenter plus
tard redéclenche bien une reprise complète.

## Les fichiers d'environnement ne sont jamais versionnés

`.gitignore` couvre `.env*` et `*.env`, avec la seule exception de `.env.example`. Cela inclut les
sauvegardes datées que l'on garde parfois à la racine avant une rotation.
