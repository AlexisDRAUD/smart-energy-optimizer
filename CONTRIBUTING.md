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
Services : `collector`, `etl`, `ml`, `api`, `web`, `common`, `infra`, `db`.

Chacun pousse ses propres commits. Personne ne pousse le code d'un autre sous son nom,
l'historique sert de preuve de contribution individuelle.

## Demandes de fusion

- La branche principale est protegee, aucun envoi direct.
- Une approbation minimum.
- La chaine d'integration doit etre au vert (des qu'elle existe).
- Une demande de fusion qui touche un contrat partage (schemas de l'API, paquet commun,
  migrations) previent explicitement les personnes concernees.

### Une exception

Le role administrateur du depot figure dans la liste de contournement de la regle. En pratique,
le Tech Lead peut pousser directement sur la branche principale. Cette exception existe pour
debloquer une situation où personne n'est disponible pour relire, typiquement l'amorcage du
projet ou un correctif pendant la demonstration. Elle ne sert pas a éviter la revue : un
contournement se signale a l'équipe.
Tous les autres membres passent par une demande de fusion, sans exception.

## Ce qui ne se pousse jamais

Fichier `.env`, identifiants, adresses de serveurs en dur, jeux de donnees, artefacts de
modeles, dossiers d'IDE.
