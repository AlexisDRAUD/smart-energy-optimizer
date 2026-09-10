# Interface utilisateur

Livrable EC05 avec `architecture.md` et `api-contract.md`. Décrit les écrans, ce que chacun affiche
et d'où viennent les chiffres.

Application React servie par nginx, routage par ancre, accès par compte et rôle.

## Les écrans

| Écran | Ce qu'il montre | Ce qu'il appelle |
|---|---|---|
| **Vue d'ensemble** | consommation totale, prévision à deux heures et écart, graphique réel et futur, alertes critiques | `/overview`, `/consumption-chart`, `/alerts`, `/sites/{id}/latest` |
| **Alertes** | compteurs par sévérité, répartition par jour, table filtrable, acquittement | `/alerts` |
| **Sites** | référentiel des sites, type, capacité, état | `/sites`, `/overview` |
| **Modèle H+2** | modèle en service, horizon, performance comparée aux références | `/predictions/latest`, `/model`, `/model/performance`, `/predictions` |
| **Historique** | consommation cumulée sur une période, complétude, points imputés | `/readings` |
| **Qualité des données** | complétude par jour et par site, état des capteurs | `/quality`, `/quality/sensors` |
| **Paramètres** | préférences d'affichage | aucun |

## Les indicateurs métier

Trois chiffres portent le dashboard, et ils sont calculés à la volée par l'API à partir du dernier
relevé valide de chaque site.

- **Consommation totale**, somme des derniers relevés des sites retenus.
- **Taux de charge moyen**, rapport de cette consommation à la somme des capacités déclarées.
- **Écart à la prévision**, différence entre le dernier relevé et la prévision qui le visait.

Un relevé n'est retenu que s'il porte une consommation non nulle et une qualité qui n'est pas
critique. Les sites écartés sont listés et l'agrégat est marqué incomplet, plutôt que d'être compté
à zéro. C'est ce qui évite qu'une panne de capteur se lise à l'écran comme une baisse de
consommation.

## Deux origines d'alertes

La table des alertes mélange deux provenances, et la colonne d'origine les distingue.

Les alertes **de la source** décrivent ce qui est constaté : dépassement de seuil, pic, panne de
capteur. Le backend les recopie sans y appliquer de règle.

Les alertes **de prévision**, de type `forecast`, sont produites par le projet lui-même. Elles
signalent une montée de charge attendue dans les deux heures, avant qu'elle ne soit mesurée. C'est
le seul cas où le produit anticipe au lieu de constater.

L'acquittement est local dans les deux cas et survit à un rechargement des alertes de la source.

## Le graphique

Le graphique de consommation trace le passé et le futur sur un seul repère, avec une échelle
verticale commune, une zone teintée pour la partie à venir et un repère « maintenant ».

Il est sous-échantillonné **côté serveur**, par un algorithme LTTB qui garde la forme de la courbe
en réduisant le nombre de points transmis à six cents par série. Trois propriétés le rendent
utilisable ici :

- les valeurs manquantes sont conservées, elles ne sont jamais lissées ni comblées,
- chaque segment continu reçoit un budget de points proportionnel à sa longueur,
- la complétude et la comparaison entre prévision et réel sont calculées sur la série **native**
  complète, avant réduction, donc les chiffres affichés ne dépendent pas de l'affichage.

Le front ne fait que découper les tracés là où le serveur signale une coupure. Un trou de données se
voit comme un trou.

## Rafraîchissement et états

Les pages qui suivent des données vivantes se rafraîchissent toutes les soixante secondes. Le
rafraîchissement se suspend quand l'onglet passe en arrière-plan et reprend au retour, et une requête
en cours est annulée si une nouvelle part.

Trois états sont traités explicitement :

- **chargement**, message dédié,
- **erreur sans données**, message et bouton pour réessayer,
- **erreur avec données déjà affichées**, l'écran garde les dernières valeurs reçues et prévient
  qu'elles ne sont plus à jour.

Ce troisième cas est le plus important en exploitation : une coupure passagère ne doit pas vider
l'écran, mais elle ne doit pas non plus faire croire que tout va bien.

Sur une réponse d'authentification expirée, le client rejoue l'appel une fois après renouvellement du
jeton, et ne renvoie vers l'écran de connexion que si le renouvellement échoue.

## Accès et rôles

Trois rôles, appliqués côté API route par route. Le front masque ce qui n'est pas permis, mais ce
n'est pas lui qui décide.

| Rôle | Peut |
|---|---|
| `viewer` | consulter tous les écrans |
| `operator` | plus l'acquittement des alertes |
| `admin` | plus la gestion des comptes |

## Aucune donnée inventée

L'interface n'affiche que ce que l'API renvoie. Aucune valeur aléatoire, aucun jeu de données
fabriqué, aucune valeur par défaut de confort dans les tracés. Une consommation absente s'affiche
comme mesure manquante, pas comme zéro.

Cela se vérifie dans le code : aucune valeur aléatoire, aucun jeu de données codé en dur dans
`services/web/src`. Le coût est assumé, tant qu'un étage de la chaîne n'a pas produit de donnée,
l'écran correspondant est vide.

## Ce qui n'est pas fait

- **Pas de recommandations** affichées à l'exploitant. Le produit dit ce qui se passe et ce qui va
  se passer, y compris par l'alerte d'anticipation, mais il ne dit pas quoi faire.
- **Pas d'alerte sortante.** Les alertes sont affichées et acquittées, rien n'est envoyé par courriel
  ni sur un canal d'équipe.
- **Pas de bandeau de fraîcheur côté serveur.** L'heure de dernière synchronisation affichée est
  celle du navigateur, alors que l'API expose l'avancement réel de l'ETL sur une route dédiée.
- **Pas d'export** des séries affichées.
