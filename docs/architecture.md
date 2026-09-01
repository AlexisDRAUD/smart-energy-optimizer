# Architecture

## Composants

| Composant | Role | Regime |
|---|---|---|
| `services/collector` | interroge la source et ecrit le brut | permanent, 1 min |
| `services/etl` | controle, repare, agrege, ecrit le transforme | planifie |
| `services/ml` | entraine, evalue, publie dans MLflow | a la demande |
| `services/api` | expose les donnees, sert les predictions, emet les alertes | permanent |
| `services/web` | dashboard | permanent |
