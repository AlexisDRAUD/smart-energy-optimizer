# Smart Energy Optimizer

Plateforme de collecte, d'analyse et de prevision de la consommation electrique de 7 sites.
Projet EnerVision, promotion EADL 2025, groupe 1.

## Ce que fait le produit

- Collecte une mesure par minute et par site depuis l'API de la source.
- Stocke la donnee brute sans la transformer, puis produit une couche transformee exploitable.
- Repare les courtes valeurs manquantes par interpolation, en gardant la valeur d'origine.
- Predit la consommation et publie la prediction.
- Leve des alertes sur les depassements de seuil.

## Demarrer

```bash
cp .env.example.example .env.example
# remplir POSTGRES_PASSWORD et JWT_SECRET_KEY, verifier SOURCE_API_BASE_URL
docker compose up
```

Le detail est dans `docs/setup.md`.

Les services demarrent dans cet ordre :

1. `db`, PostgreSQL 16, sur un volume vide au premier lancement.
2. `migrate`, qui applique les migrations Alembic, cree les comptes, reprend l'historique de
   la source, puis s'arrete.
3. `api`, `collector`, `etl` et `supervisor`, qui attendent que `migrate` se termine sans
   erreur.
4. `web`, le dashboard, qui attend que l'API soit saine.

`migrate`, `api`, `collector`, `etl` et `supervisor` utilisent la meme image backend avec des
commandes differentes. `supervisor` surveille l'erreur du modele en production et decide des
reentrainements, voir `docs/ml-supervision.md`.

Comptez une dizaine de secondes pour la reprise d'historique, puis une trentaine pour la
premiere transformation, avant que le dashboard affiche quelque chose. Le dashboard repond sur
`http://localhost`, l'API sur `http://localhost:8080`.

## D'ou viennent les donnees

**Aucune donnee n'est inventee au demarrage.** Les sites, les mesures, l'etat des capteurs, les
predictions et les alertes viennent de la chaine elle-meme : le collecteur interroge la source,
l'ETL transforme, l'API calcule. La base est vide au premier `docker compose up`, puis se
remplit toute seule.

La seule chose inseree au demarrage, ce sont les comptes, parce que rien d'autre ne les cree.
Ils portent le mot de passe de `SEED_USER_PASSWORD`, `EnerVisionDemo2026!` par defaut :

| Nom | E-mail | Role |
|---|---|---|
| Camille Martin | `camille.martin@enervision.demo` | `admin` |
| Lucas Bernard | `lucas.bernard@enervision.demo` | `operator` |
| Marc Legrand | `marc.legrand@enervision.demo` | `viewer` |

Le schema n'existe que dans `services/backend/alembic/versions/`. Aucun fichier SQL n'est joue
par l'image PostgreSQL, et personne ne cree de table a la main.

## Documentation

Tout est dans `docs/`.

**Pour demarrer**

- `setup.md` : installer et travailler au quotidien. A lire en premier.
- `configuration.md` : toutes les variables du `.env`, ce qu'elles font et ce qu'elles coutent.
- `runbook.md` : verifier que la chaine tourne, amorcer, rejouer, diagnostiquer une panne.

**Les contrats, ils font foi**

- `data-contract.md` : les tables, qui ecrit quoi, ce qui ne s'y met pas.
- `api-contract.md` : les routes, l'authentification, les codes de reponse.

**Comprendre et contribuer**

- `architecture.md` : les composants, le flux, la cadence, le stockage, la structure du depot.
- `tests-et-qualite.md` : lancer les tests, les outils, les regles.
- `ci.md` : la chaine d'integration.
- `security.md` : ce qui est protege, et ce qui ne l'est pas encore.

**Le reste**

- `deploiement.md` : la VM de l'ecole. Prevu, pas encore fait.
- `ml.md` : le modele. Hors de ce lot.
- `ml-supervision.md` : le superviseur du modele, ses regles et ses decisions.
- `adr/` : les decisions structurantes et leurs consequences.

Les regles de contribution sont dans `CONTRIBUTING.md`.
