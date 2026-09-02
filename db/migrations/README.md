# Migrations

Le schema de la base n'existe que dans ce dossier. Personne ne cree une table a la main.

## Comment ces fichiers sont joues

Le dossier est monte dans `/docker-entrypoint-initdb.d` du conteneur PostgreSQL. L'image ne
joue ces fichiers **qu'a la creation du volume**, par ordre alphabetique du nom. Un fichier
ajoute plus tard n'est pas rejoue sur une base existante.

Consequence assumee pour ce projet : il n'y a pas de migration incrementale. Pour prendre en
compte un changement de schema, on recree la base.

```bash
docker compose down -v
docker compose up -d
```

Le `-v` supprime le volume, donc les donnees. La couche brute se reconstruit par l'amorcage,
voir `docs/runbook.md`.

## Nommage

`NNN_sujet.sql`, numerotation a trois chiffres. Le numero fixe l'ordre d'execution.

## Regle

Une modification de ce dossier passe par une demande de fusion et previent les personnes qui
tiennent le collecteur, l'ETL et l'API. Le contrat de donnees `docs/data-contract.md` et ces
fichiers doivent dire la meme chose. Si l'un des deux change, l'autre change dans la meme
demande de fusion.
