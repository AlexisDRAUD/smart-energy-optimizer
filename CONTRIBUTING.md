# Contribuer

## Branches

```
EADL_2025_NIORT_G1/<tache>
```

Exemple : `EADL_2025_NIORT_G1/setup-docker-pipeline`. La convention est imposee par les
consignes, elle ne se discute pas.

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

## Ce qui ne se pousse jamais

Fichier `.env`, identifiants, adresses de serveurs en dur, jeux de donnees, artefacts de
modeles, dossiers d'IDE.
