# Installation

Comment obtenir, sur n'importe quel poste, exactement la même base que les autres.

Pour la VM, voir `deploiement.md`. Pour la liste des réglages, voir `configuration.md`.

## Le principe

Personne ne crée de table à la main, et personne ne s'envoie de sauvegarde. Le schéma n'existe
que dans `services/backend/alembic/versions/`, et c'est le dépôt qui le distribue.

Alembic compare les modèles SQLAlchemy de `services/backend/app/db/models/` à l'état réel de la
base et applique les fichiers de `versions/` qui manquent. Chaque base garde la liste de ce
qu'elle a déjà joué dans une table `alembic_version`.

Un service dédié applique tout cela une fois au démarrage :

```
db  ->  migrate  ->  api, collector, etl  ->  web
```

`migrate` attend que PostgreSQL réponde, joue `alembic upgrade head`, crée les comptes de
démonstration, reprend l'historique, puis **s'arrête**. C'est normal, c'est un job et pas un
service. Les autres ne démarrent que s'il s'est terminé sans erreur.

`migrate` est une étape à part et pas un bout du démarrage de l'API, parce que le schéma
appartient à la base et pas à un composant. Le jour où le collecteur démarre en premier, il
trouve une base prête, et plusieurs copies de l'API qui démarrent ensemble ne se lancent pas
toutes dans la migration en parallèle.

C'est la même image que l'API, avec une commande différente.

## Première installation

```bash
git clone <le depot>
cd smart-energy-optimizer

cp .env.example.example .env.example
```

Ouvrir `.env` et remplir les deux secrets, `POSTGRES_PASSWORD` et `JWT_SECRET_KEY` :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Reporter le mot de passe dans `DATABASE_URL`, qui sert aux commandes lancées hors docker.
Vérifier aussi `SOURCE_API_BASE_URL`, l'adresse de l'API du formateur.

Ces valeurs sont propres à chaque poste, elles ne se partagent pas et le fichier n'est jamais
commité.

Puis :

```bash
docker compose up
```

Ce premier lancement est long, il construit les images. Ensuite il enchaîne :

1. `db` démarre sur un volume vide, PostgreSQL s'y installe ;
2. `migrate` applique le schéma, crée les comptes, reprend l'historique et s'arrête ;
3. `api`, `collector` et `etl` démarrent, `web` attend que l'API soit saine.

Comptez une dizaine de secondes pour la reprise d'historique, puis une trentaine pour la
première transformation, avant que le dashboard affiche quelque chose.

Le dashboard répond sur `http://localhost` et l'API sur `http://localhost:8080`. Les comptes de
démonstration sont dans le `README.md`.

## Au quotidien

```bash
docker compose up -d          # le matin, -d rend la main au terminal
docker compose ps             # qui tourne
docker compose logs -f etl    # suivre les journaux d'un conteneur
docker compose stop           # le soir, ou laisser tourner
```

**Le piège à connaître.** `docker compose up` ne reconstruit pas l'image quand le code change,
il réutilise celle qui existe déjà. Après avoir modifié du Python ou récupéré du code :

```bash
docker compose up -d --build
```

Deuxième piège, de la même famille : `docker compose start` relance le conteneur **existant**,
avec l'ancienne image. Après un `build`, il faut `docker compose up -d --force-recreate <service>`,
sinon la modification n'a aucun effet et rien ne le signale.

**Où vivent les données.** Dans le volume `db_data`, en dehors des conteneurs. C'est ce qui
permet de détruire et recréer les conteneurs sans rien perdre.

| Commande | Les données |
|---|---|
| `up`, `stop`, `restart`, `down` | intactes |
| `down -v` | **effacées** |

Le `-v` est le seul destructeur.

## Après avoir récupéré du code

```bash
git pull
docker compose up -d --build
```

S'il y a une nouvelle migration, `migrate` la détecte et l'applique sur la base existante. Les
données restent. **Pas besoin de `down -v`.**

## Quand le schéma change

Celui qui change le schéma modifie un modèle dans `services/backend/app/db/models/`, puis
génère la migration correspondante :

```bash
cd services/backend
DATABASE_URL=postgresql+psycopg://seo:<mot de passe>@127.0.0.1:5432/seo \
  python -m alembic revision --autogenerate -m "description du changement"
```

Le fichier généré se **relit toujours** avant d'être commité. Alembic voit ce que les modèles
déclarent, il ne devine ni une reprise de données ni un renommage : une colonne renommée se
présente comme une suppression suivie d'un ajout, et les valeurs sont perdues.

La migration part dans la même demande de fusion que le modèle et que `data-contract.md`, et la
description de la demande le dit, pour que les autres sachent qu'ils doivent relancer
`docker compose up -d --build`.

## Repartir de zéro

```bash
docker compose down -v && docker compose up
```

Sans gravité en local : la base n'est pas la source de vérité, elle se reconstruit par la
reprise d'historique. **À ne pas faire sur la VM** : l'endpoint historique de la source
régénère ses données à chaque appel, une seconde reprise ne redonnerait pas les mêmes valeurs.

## Travailler sans Docker

Les tests du backend et la génération de migrations tournent en local. Une seule installation à
faire :

```bash
python3 -m venv .venv
.venv/bin/pip install -e packages/features
.venv/bin/pip install -r services/backend/requirements.txt
```

Si `python3 -m venv` échoue, il manque le paquet `python3-venv`.

Les tests créent et détruisent leur propre base, `seo_test`, à côté de la base de travail. Il
suffit donc que `db` tourne. La commande est dans `tests-et-qualite.md`.
