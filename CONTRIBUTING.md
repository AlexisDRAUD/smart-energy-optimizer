# Contribuer

## Modele de branches

Deux branches longues.

- `dev` : branche d'integration, branche par defaut du depot. C'est de la que partent toutes
  les branches de travail et c'est la qu'elles reviennent.
- `main` : etat demontrable. `dev` y est fusionnee aux jalons.

```
main  <-- fusion aux jalons --  dev  <-- demandes de fusion --  branches de travail
```

## Branches de travail

```
EADL_2025_NIORT_G1/<tache>
```

Exemple : `EADL_2025_NIORT_G1/setup-docker-pipeline`. La convention est imposee par les
consignes, elle ne se discute pas.

Une branche de travail part toujours de `dev` :

```bash
git switch dev && git pull
git switch -c EADL_2025_NIORT_G1/ma-tache
```

Une tache, une branche, une fusion dans la journee. Une branche qui vit trois jours devient
un conflit a elle toute seule.

## Commits

```
type(service): phrase courte a l'infinitif ou au present
```

Types : `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`.
Portees : `backend`, `ml`, `web`, `features`, `infra`, `db`, `docs`.

`backend` couvre le collecteur, l'ETL et l'API, qui vivent dans la meme image. Quand un
commit ne touche qu'un des trois, la phrase le dit : `feat(backend): ajouter la boucle du
collecteur`.

Chacun pousse ses propres commits. Personne ne pousse le code d'un autre sous son nom,
l'historique sert de preuve de contribution individuelle.

## Demandes de fusion

- La branche principale est protegee, aucun envoi direct.
- Une approbation minimum.
- La chaine d'integration doit etre au vert (des qu'elle existe).
- Une demande de fusion qui touche un contrat partage (schemas de l'API, `packages/features`,
  migrations, modeles de `app/db/`) previent explicitement les personnes concernees.
- Une demande de fusion qui ajoute une migration le dit dans sa description : les autres
  devront relancer `docker compose up` apres l'avoir recuperee.

### Cycle de vie

1. Fusionner `dev` dans la branche et verifier que tout tourne encore.
2. Ouvrir la demande de fusion vers `dev`. Titre au format des commits, description courte :
   ce que ca fait, ce qu'il faut regarder.
3. Une autre personne relit et approuve. L'auteur ne peut pas approuver sa propre demande.
4. L'auteur fusionne une fois l'approbation obtenue, puis supprime la branche de travail.

Une demande de fusion ouverte depuis plus d'une journee est un signal : soit la tache etait
trop grosse, soit personne ne relit. Dans les deux cas, le dire.

### Relire une demande de fusion

Relire n'est pas chercher la faute. On regarde, dans cet ordre :

- est-ce que ca fait ce que la carte demande
- est-ce qu'une des regles de `CLAUDE.md` est enfreinte (secrets, couche brute, formules
  dupliquees, logique metier dans le front)
- est-ce que c'est lisible par quelqu'un d'autre dans six mois

### Une exception

Le role administrateur du depot figure dans la liste de contournement de la regle. En pratique,
le Tech Lead peut pousser directement sur la branche principale. Cette exception existe pour
debloquer une situation où personne n'est disponible pour relire, typiquement l'amorcage du
projet ou un correctif pendant la demonstration. Elle ne sert pas a éviter la revue : un
contournement se signale a l'équipe.
Tous les autres membres passent par une demande de fusion, sans exception.

## Fusion de `dev` dans `main`

`main` represente ce qui est demontrable. Elle bouge aux jalons. La fusion est declenchee par le Tech Lead, apres verification
que `dev` tourne de bout en bout via `docker compose`.

Le sens est toujours `dev` vers `main`. On ne travaille jamais directement sur `main`.


## Ce qui ne se pousse jamais

Fichier `.env`, identifiants, adresses de serveurs en dur, jeux de donnees, artefacts de
modeles, dossiers d'IDE.
