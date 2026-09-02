# Smart Energy Optimizer

Plateforme de collecte, d'analyse et de prevision de la consommation electrique de 7 sites.
Projet EnerVision, promotion EADL 2025, groupe 1.

## Ce que fait le produit

- Collecte une mesure par minute et par site depuis l'API de la source.
- Stocke la donnee brute sans la transformer, puis produit une couche transformee exploitable.
- Predit la consommation et publie la prediction.
- Leve des alertes sur les depassements de seuil.
- Propose des actions d'economie chiffrees en kWh.

## Demarrer PostgreSQL

```bash
cp .env.example .env
docker compose up -d db
./scripts/verify-postgres-init.sh
```

PostgreSQL execute `db/migrations/001_schema.sql` uniquement lors de la creation
d'un volume vide. Le script de verification confirme que les dix tables du
schema de reference existent sans supprimer de donnees.

Pour inserer les donnees mock dans les tables de demonstration :

```bash
MOCK_DATA_CONFIRM=1 ./scripts/seed-mock-data.sh
```

Le seed remplace les donnees des sites mock `LYO-01`, `GRE-01` et `NAN-01`,
puis ajoute 24 heures de mesures par minute, les etats des capteurs, la
qualite, les predictions, une alerte et l'execution ETL mock. La confirmation
explicite empeche son usage accidentel sur une base contenant des donnees
reelles.

Le seed cree egalement les comptes suivants avec le mot de passe
`EnerVisionDemo2026!` :

| Nom | E-mail | Role |
|---|---|---|
| Camille Martin | `camille.martin@enervision.demo` | `admin` |
| Lucas Bernard | `lucas.bernard@enervision.demo` | `operator` |
| Marc Legrand | `marc.legrand@enervision.demo` | `viewer` |

## Documentation

Tout est dans `docs/`. Commencer par `docs/architecture.md`.
Les regles de contribution sont dans `CONTRIBUTING.md`.
