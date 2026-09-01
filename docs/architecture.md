# Architecture

## Composants

| Composant | Role | Regime |
|---|---|---|
| `services/collector` | interroge la source et ecrit le brut | permanent, 1 min |
| `services/etl` | controle, repare, agrege, ecrit le transforme | permanent, 15 min |
| `services/ml` | entraine, evalue, publie dans MLflow | a la demande, repousse |
| `services/api` | expose les donnees, sert les predictions, emet les alertes | permanent |
| `services/web` | dashboard | permanent |

Le schema d'ensemble est dans `architecture.mmd`, a coller sur https://mermaid.live.

## Cadence

Le collecteur et le job de transformation portent leur cadence eux-memes, par une boucle qui
dort entre deux passes. Pas de cron, pas d'ordonnanceur. Un processus arrete ne rattrape rien,
ce qui est coherent avec notre position sur les trous de collecte.

## Stockage

Un seul PostgreSQL, deux couches. La couche brute en JSONB, insertion seulement, partitionnée
par mois. La couche transformée en tables typées, avec une cle unique sur site et horodatage
qui rend le job de transformation rejouable. Le schema n'existe que dans `db/migrations/`,
voir `data-contract.md` pour le detail des colonnes.

## Exposition

Le compose ne publie que deux ports vers l'exterieur, l'API et le dashboard. La base et MLflow
sont limites a la machine hote. Le detail est dans `security.md`.
