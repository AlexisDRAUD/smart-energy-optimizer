# Déploiement sur la VM

La cible est une **VM de l'école**, sur le même réseau que l'API du formateur.

> **Ce document n'a pas encore été exécuté.** Il décrit la procédure prévue, pas une
> installation constatée. Le déploiement fait l'objet d'une branche à part. Ce qui suit sera
> corrigé au premier passage réel.

## Le principe

Le même `docker-compose.yml` qu'en local, sans une ligne de différence. Tout ce qui change
passe par le `.env`. Voir `configuration.md` pour la liste complète.

Dupliquer le compose aurait produit deux fichiers qui divergent : celui de la VM ne se teste
nulle part, et l'écart se découvre le jour de la démonstration.

## Ce qui change dans le `.env`

| Variable | En local | Sur la VM | Pourquoi |
|---|---|---|---|
| `WEB_BIND` | `127.0.0.1` | `0.0.0.0` | sinon le dashboard n'est joignable que depuis la VM elle-même |
| `COOKIE_SECURE` | `false` | `true` **si HTTPS** | le cookie de session ne doit pas circuler en clair. À laisser à `false` tant que la VM est en HTTP simple, sinon la connexion échoue |
| `POSTGRES_PASSWORD` | valeur de poste | un vrai secret, propre à la VM | |
| `JWT_SECRET_KEY` | valeur de poste | un vrai secret, propre à la VM | un jeton signé sur un poste ne doit pas être accepté par la VM |
| `SEED_USER_PASSWORD` | `EnerVisionDemo2026!` | à changer | les comptes sont exposés sur le réseau |
| `BACKFILL_DAYS` | `7` | au choix | la VM a le temps, mais le démarrage s'allonge d'autant |
| `SOURCE_API_BASE_URL` | adresse de la source | idem, **à vérifier depuis la VM** | l'adresse peut différer selon le segment réseau |

Tout le reste garde sa valeur.

Un fichier `.env.vm.example` sera ajouté à la racine avec la branche de déploiement.

## Première installation

```bash
git clone <le depot>
cd smart-energy-optimizer

cp .env.example .env
```

Éditer le `.env` selon le tableau ci-dessus. Générer les deux secrets :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Vérifier que la source répond **depuis la VM**, avant de lancer quoi que ce soit :

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$SOURCE_API_BASE_URL/api/v1/sites"
```

Un `200` attendu. Sans cela le collecteur tournera dans le vide et la reprise d'historique
sera vide, sans que le démarrage échoue.

Puis :

```bash
docker compose up -d --build
```

Le premier démarrage construit les images, applique le schéma, crée les comptes et reprend
l'historique. Compter quelques minutes pour la construction, puis une dizaine de secondes pour
la reprise.

## Vérifier que ça tourne

Dans cet ordre, c'est celui du flux :

```bash
docker compose ps                                    # les six services sont Up
docker compose logs migrate | tail -20               # la reprise a-t-elle ecrit
docker compose logs -f collector                     # un passage par minute
docker compose logs -f etl                           # un passage par minute
```

Puis les compteurs, qui doivent tous être non nuls :

```bash
docker compose exec db psql -U seo -d seo -c "
SELECT (SELECT count(*) FROM raw_readings) brut,
       (SELECT count(*) FROM readings) mesures,
       (SELECT count(*) FROM sites) sites,
       (SELECT count(*) FROM etl_runs) passages"
```

Enfin le dashboard, sur `http://<adresse de la VM>:<WEB_PORT>`.

Le détail du diagnostic quand un de ces points ne répond pas est dans `runbook.md`.

## Mettre à jour

```bash
git pull
docker compose up -d --build
```

Les migrations en attente s'appliquent sur la base existante, les données restent. Pas de
`down -v` : il détruirait l'historique repris, et une seconde reprise ne redonnerait pas les
mêmes valeurs, l'endpoint historique de la source régénérant ses données à chaque appel.

## Ce qui n'est pas fait

- **Pas de HTTPS.** Il faudrait un reverse proxy devant le conteneur `web`, et `COOKIE_SECURE`
  à `true` une fois en place.
- **Pas de sauvegarde de la base.** Assumé : la couche brute se reconstruit par une nouvelle
  reprise, avec la réserve ci-dessus sur la régénération des données.
- **Pas de démarrage automatique au boot de la VM.** Les conteneurs sont en
  `restart: unless-stopped`, ils repartent si Docker redémarre, mais Docker lui-même doit être
  activé au démarrage de la machine.
- **Pas de rotation des journaux.** Les journaux Docker grossissent sans limite.
