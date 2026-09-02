# Modele

## Cible

Consommation en kWh a **deux heures**, emise a la minute. L'horizon vient du temps qu'il faut
a un exploitant pour agir : reperer le risque, decider, prevenir, puis decaler une recharge ou
arreter une ventilation. A trente minutes il reste le temps de constater, pas d'agir.

Contrepartie a assumer devant le jury : l'erreur croit avec l'horizon. C'est precisement
pourquoi les deux references sont publiees a cote. Une prediction a deux heures qui bat la
derniere valeur connue vaut mieux qu'une prediction a trente minutes qui l'egale.

## Variables d'entree

Toutes calculees par `packages/common`, jamais ailleurs. Une formule dupliquee entre
l'entrainement et le service degrade le modele en production sans faire echouer un seul test.

Familles retenues : valeurs recentes du site, agregats glissants, variables de calendrier
recalculees depuis l'horodatage, meteo (temperature, humidite, ensoleillement), type de site.

## Decoupage des donnees

Decoupage **chronologique strict**. L'entrainement sur le passe, la validation sur la periode
suivante, jamais de tirage aleatoire. Un tirage aleatoire sur une serie temporelle donne un
score flatteur et faux.

## Modeles

- Modele retenu : arbres renforces par gradient. Ils gerent les valeurs manquantes, ils
  s'expliquent et ils s'entrainent en quelques secondes a cette volumetrie.
- References publiees a cote, sur le dashboard : la persistance (la derniere valeur connue)
  et une regression lineaire.

La grille ne note pas la precision du modele. Elle note qu'il soit entraine, versionne,
deploye, surveille et documente. Afficher ce qu'il faut battre est ce qui rend la
surveillance lisible.

## Metriques

Erreur absolue moyenne et erreur quadratique moyenne, par site et sur l'ensemble, comparees
aux deux references. Enregistrees dans MLflow a chaque entrainement.

## Publication d'une version

1. Lancer l'entrainement, il cree un essai dans MLflow.
2. Comparer aux references et a la version en place.
3. Enregistrer le modele dans le registre et lui donner l'etiquette production.
4. Redemarrer l'API, elle charge la version marquee production au demarrage.

Si MLflow ne repond pas, l'API demarre avec la derniere copie locale du modele. Un service
qui refuse de demarrer parce qu'un service annexe est absent est un incident de demonstration
garanti.

## Surveillance

Chaque prediction emise est comparee a la mesure reelle quand elle arrive, soit 1440
predictions notees par jour et par site. L'ecart est stocke et affiche.

La cadence d'emission est la minute et non le quart d'heure. Ce n'est pas pour la fraicheur,
une prediction a trente minutes recalculee chaque minute ne bouge presque pas. C'est pour la
surveillance : une erreur moyenne calculee sur 1440 points est plus stable que sur 96.
