# Runbook

## Démarrer et arrêter

```bash
docker compose up -d
docker compose ps
docker compose logs -f collector
docker compose down
```

## Amorçage,à faire une seule fois

```bash
# 1. import des CSV fournis
TODO: A complété
# 2. reprise de l'historique depuis l'API, la profondeur est un choix documente
TODO: A complété
```

Ne pas relancer la reprise pour combler un trou. L'endpoint historique regénère les données
à chaque appel, une deuxième reprise écrirait des valeurs différentes de celles déjà en base.

## Rejouer une fenêtre de transformation

```bash
TODO: A complété
```

Sans risque, la cle unique sur site et horodatage empêche les doublons.

## Sauvegarde

Le depot porte le code et les migrations. La base de la VM n'est pas sauvegardée, et elle n'a
pas a l'être : la couche brute se reconstruit depuis les CSV et une nouvelle reprise, avec la
reserve ci-dessus sur la regeneration.
