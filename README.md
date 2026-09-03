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

C'est tout. Trois services demarrent dans cet ordre :

1. `db`, PostgreSQL 16, sur un volume vide au premier lancement.
2. `migrate`, qui applique les migrations Alembic puis insere les donnees de
   demonstration, et s'arrete.
3. `api`, qui ne demarre que quand `migrate` s'est terminee sans erreur.

`migrate` et `api` sont la meme image lancee avec deux commandes differentes. Le
collecteur et l'ETL la rejoindront de la meme facon quand leur code arrivera.

Le schema n'existe que dans `services/backend/alembic/versions/`. Aucun fichier SQL
n'est joue par l'image PostgreSQL, et personne ne cree de table a la main.

Pour repartir d'une base vide :

```bash
docker compose down -v && docker compose up
```

Les donnees de demonstration couvrent 24 heures de mesures a la minute sur les trois
sites `LYO-01`, `GRE-01` et `NAN-01`, plus les etats des capteurs, la qualite, une
alerte et une execution ETL. Le seed est rejouable : il ne fait rien si les sites
existent deja. Pour demarrer sans lui, mettre `SEED_DEMO_DATA=0` dans le `.env`.

Le seed cree egalement les comptes suivants avec le mot de passe
`EnerVisionDemo2026!` :

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
