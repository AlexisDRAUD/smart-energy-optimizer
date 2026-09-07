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

Les deux passent a la minute. Le job de transformation porte deux fenetres, qui n ont ni le meme
role ni la meme largeur.

La premiere lit le brut. Elle repart de la borne du dernier passage reussi, moins deux minutes.
Ce recouvrement n existe que pour rattraper une ligne dont la transaction n etait pas terminee
au moment de la lecture ; nos ecritures durent des millisecondes. Une fenetre large ne servirait
a rien ici et couterait cher : apres une reprise d historique, les 70 000 lignes portent toutes
le meme horodatage de reception, et une fenetre de trente minutes les relirait entierement a
chaque passage, soit une trentaine de secondes de travail pour ecrire sept lignes.

La seconde repare les valeurs nulles, sur readings et non sur le brut. Elle fait trente minutes,
et c est elle qui permet de reparer une valeur nulle une minute apres le retour de la mesure.
Retransformer une ligne brute ne repare rien, elle redonnerait la meme valeur nulle : la
reparation regarde les mesures voisines. A sept sites et un point par minute, une passe y revoit
deux cent dix lignes.

## Stockage

Un seul PostgreSQL, deux couches. La couche brute en JSONB, insertion seulement, non
partitionnée : PostgreSQL exige qu'une clé unique porte la colonne de partitionnement, ce qui
ferait sauter la déduplication sur `(site_id, measured_at)`. Voir `data-contract.md`. La couche transformée en tables typées, avec une cle unique sur site et horodatage
qui rend le job de transformation rejouable. Le schema n'existe que dans
`services/backend/alembic/versions/`, applique par Alembic,
voir `data-contract.md` pour le detail des colonnes.

## Exposition

Le compose ne publie que deux ports vers l'exterieur, l'API et le dashboard. La base et MLflow
sont limites a la machine hote. Le detail est dans `security.md`.
