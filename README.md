# Smart Energy Optimizer

Plateforme de collecte, d'analyse et de prevision de la consommation electrique de 7 sites.
Projet EnerVision, promotion EADL 2025, groupe 1.

## Ce que fait le produit

- Collecte une mesure par minute et par site depuis l'API de la source.
- Stocke la donnee brute sans la transformer, puis produit une couche transformee exploitable.
- Predit la consommation et publie la prediction.
- Leve des alertes sur les depassements de seuil.
- Propose des actions d'economie chiffrees en kWh.

## Demarrer

```bash
cp .env.example .env      # puis remplir les deux secrets
docker compose up -d
```

La procedure complete, et quoi faire quand le schema de la base change, sont dans
`docs/setup.md`.

## Documentation

Tout est dans `docs/`. Commencer par `docs/architecture.md`.
Les regles de contribution sont dans `CONTRIBUTING.md`.
