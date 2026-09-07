# Smart Energy Optimizer

Plateforme de collecte, d'analyse et de prevision de la consommation electrique de 7 sites.
Projet EnerVision, promotion EADL 2025, groupe 1.

## Ce que fait le produit

- Collecte une mesure par minute et par site depuis l'API de la source.
- Stocke la donnee brute sans la transformer, puis produit une couche transformee exploitable.
- Predit la consommation et publie la prediction.
- Leve des alertes sur les depassements de seuil.
- Propose des actions d'economie chiffrees en kWh.

## Demarrer l'environnement

```bash
cp .env.example .env
docker compose up
```

C'est tout. Les services demarrent dans cet ordre :

1. `db`, PostgreSQL 16, sur un volume vide au premier lancement.
2. `migrate`, qui applique les migrations Alembic puis insere les donnees de
   demonstration, et s'arrete.
3. `api` et l'ETL ponctuel, qui attendent que `migrate` se termine sans erreur.
4. `web`, qui attend que l'API soit saine.

`migrate`, `api` et `etl` utilisent la meme image backend avec des commandes
différentes. L'ETL peut être relancé à la demande avec `docker compose run --rm etl`.

Le schema n'existe que dans `services/backend/alembic/versions/`. Aucun fichier SQL
n'est joue par l'image PostgreSQL, et personne ne cree de table a la main.

Pour repartir d'une base vide :

```bash
docker compose down -v && docker compose up
```

Le demarrage ne cree aucune mesure ni aucun site. Les sites, les mesures, les
predictions et les alertes viennent de la chaine elle-meme : le collecteur
interroge la source, l ETL transforme, l API calcule. La base est donc vide au
premier `docker compose up`, puis se remplit toute seule.

La seule chose inseree au demarrage, ce sont les comptes, parce que rien d autre
ne les cree. Ils portent le mot de passe `EnerVisionDemo2026!` :

| Nom | E-mail | Role |
|---|---|---|
| Camille Martin | `camille.martin@enervision.demo` | `admin` |
| Lucas Bernard | `lucas.bernard@enervision.demo` | `operator` |
| Marc Legrand | `marc.legrand@enervision.demo` | `viewer` |

## Documentation

Tout est dans `docs/`.

- `setup.md` : installer, travailler au quotidien, changer le schema. A lire en premier.
- `architecture.md` : les composants, les images, la cadence, le stockage.
- `structure.md` : a quoi sert chaque dossier, et surtout ce qui n'a pas a y aller.
- `data-contract.md` et `api-contract.md` : les contrats, ils font foi.
- `decisions.md` : le registre des decisions et leurs amendements.
- `runbook.md` : diagnostiquer quand ca ne marche pas.
- `quality.md`, `testing.md`, `security.md`, `ml.md` : le reste.

Les regles de contribution sont dans `CONTRIBUTING.md`.
