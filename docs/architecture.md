# Architecture

## Composants

Trois images, sept conteneurs. L'image `backend` est lancee plusieurs fois avec des
commandes differentes.

| Conteneur | Image | Role | Regime |
|---|---|---|---|
| `db` | postgres:16 | la base | permanent |
| `migrate` | backend | applique le schema et les donnees de demonstration | une fois, puis s'arrete |
| `collector` | backend | interroge la source et ecrit le brut | permanent, 1 min |
| `etl` | backend | controle, repare, agrege, ecrit le transforme | permanent, 1 min |
| `api` | backend | expose les donnees, sert les predictions, emet les alertes | permanent, boucle de prediction 1 min |
| `ml` | ml | entraine, evalue, publie dans MLflow | a la demande, repousse |
| `web` | web | dashboard | permanent |

**Pourquoi une seule image pour le collecteur, l'ETL et l'API.** Ils partagent la meme base,
les memes modeles et la meme cadence de livraison. Ce sont trois morceaux d'un meme programme,
pas trois services independants : un decoupage en images separees aurait produit trois jeux de
dependances a maintenir sans rien apporter, puisqu'ils se deploient de toute facon ensemble.

Ils restent dans des conteneurs separes, et c'est ce qui compte a l'execution : le collecteur
qui plante ne doit pas emporter le dashboard, et chacun se redemarre seul.

**Pourquoi le ML a son image.** Dependances lourdes qui ne servent qu'a lui (lightgbm,
scikit-learn, MLflow), et cycle de vie different : il tourne a la demande, pas en continu. Il
lit la base en SQL direct et n'y ecrit rien, donc il n'a pas besoin des modeles du backend.

La seule chose partagee entre le backend et le ML est le calcul des variables d'entree du
modele, dans `packages/features`. Voir `structure.md`.

Le schema d'ensemble est dans `architecture.mmd`, a coller sur https://mermaid.live.

## Cadence

Le collecteur et le job de transformation portent leur cadence eux-memes, par une boucle qui
dort entre deux passes. Pas de cron, pas d'ordonnanceur. Un processus arrete ne rattrape rien,
ce qui est coherent avec notre position sur les trous de collecte.

Les deux passent a la minute. Le job de transformation travaille sur une fenetre glissante de
trente minutes, il revoit donc chaque minute une trentaine de fois. A sept sites et un point
par minute, une passe relit deux cent dix lignes : la cadence ne se paie pas, et elle est ce
qui permet de reparer une valeur nulle une minute apres le retour de la mesure.

## Stockage

Un seul PostgreSQL, deux couches. La couche brute en JSONB, insertion seulement, partitionnée
par mois. La couche transformée en tables typées, avec une cle unique sur site et horodatage
qui rend le job de transformation rejouable. Le schema n'existe que dans
`services/backend/alembic/versions/`, applique par Alembic,
voir `data-contract.md` pour le detail des colonnes.

## Exposition

Le compose ne publie que deux ports vers l'exterieur, l'API et le dashboard. La base et MLflow
sont limites a la machine hote. Le detail est dans `security.md`.
