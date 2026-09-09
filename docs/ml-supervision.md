# Supervision du modèle

Le superviseur surveille, site par site, l'erreur du modèle en production et demande son
réentraînement quand elle dérive ou quand le filet hebdomadaire l'impose. Il tourne dans son
propre conteneur (`supervisor`, image `backend`, commande `python -m app.supervisor`).

## Pourquoi un superviseur

Le sujet demande un modèle surveillé en production (dérive, métriques) et une amélioration
continue. Avec deux ans d'historique par site, réentraîner à date fixe ne change rien : une
journée de plus représente 0,14 % des données. Ce qui périme un modèle, c'est un changement de
comportement du site — nouvelle machine, nouveaux horaires, capteur remplacé — et seule la
mesure de l'erreur en production le voit.

Le superviseur mesure, décide et lance. Il ne juge jamais un modèle : c'est le script
d'entraînement qui compare et promeut.

## Ce que le superviseur fait

À chaque tour, pour chaque site actif :

1. **Mesure.** Lit `predictions`, déjà notée par l'API (`actual_kwh`, `absolute_error`), et
   calcule la MAE de la version en production sur deux fenêtres : 7 jours (décision) et 24 h
   (alerte). Seule la version de la dernière prédiction émise compte : après une promotion,
   l'ancien modèle ne juge pas le nouveau.
2. **Lit le seuil** dans MLflow, par l'API REST : `drift_threshold_mae` du run qui a
   enregistré la version, à défaut `mae` holdout × tolérance.
3. **Décide**, dans cet ordre, la première règle qui conclut l'emporte :

   | Verdict | Condition | Effet |
   |---|---|---|
   | *inactif* | pas de seuil (version sans modèle dans le registre, MLflow injoignable) | WARNING, site suivant |
   | `verrou` | un lancement pour ce site il y a moins de 24 h | rien |
   | `filet` | version notée depuis au moins 7 jours et rien lancé depuis au moins 7 jours | lancement |
   | `grace` | version notée depuis moins de 24 h | rien |
   | `derive` | MAE 7 j > seuil | lancement |
   | `aucun` | MAE 7 j ≤ seuil | rien |

4. **Journalise** une ligne INFO par site : MAE 7 j, MAE 24 h, seuil, verdict, dernier
   lancement. Un WARNING quand la MAE 24 h dépasse le seuil, pour voir venir.
5. **Lance**, sur `filet` ou `derive`, en passant le `site_id` au lanceur — et rien d'autre.

### Décision 1 — fenêtre de mesure : 7 jours glissants, 24 h en alerte précoce

Une dérive est un changement durable. Une fenêtre courte confondrait un pic ponctuel ou une
panne de capteurs avec une dérive. La MAE de référence du modèle est une moyenne sur tous les
types de jours ; comparer un dimanche seul à cette moyenne déclencherait une fausse alerte
chaque week-end. La semaine est le plus petit cycle qui contient tous les types de jours : la
fenêtre de décision est de 7 jours.

À une prédiction par minute, 7 jours font 10 000 points : plus long n'améliore pas la mesure et
retarde la réaction. Une fenêtre de 24 h est calculée en plus, à titre informatif : elle
prévient, elle ne décide pas.

Après une promotion, la fenêtre repart de zéro : seules les prédictions de la version en
production comptent. La mesure est par site.

### Décision 2 — seuil de dérive : dérivé des données du modèle, jamais absolu

Un seuil absolu n'a pas de sens : un bureau à 75 kW et une usine à 850 kW n'ont pas la même
échelle. Le seuil est relatif au modèle.

À l'entraînement, les 2 mois de test sont découpés en semaines ; la MAE de chaque semaine mesure
la variabilité naturelle de l'erreur sans dérive. Le seuil est la pire de ces semaines augmentée
de 20 % — `drift_threshold_mae`, loggée dans MLflow avec le run. Au-delà, ce n'est plus du bruit
connu.

À défaut de cette métrique, le superviseur replie sur 1,5 fois la MAE de test (`mae`). Sans
aucune des deux — version sans modèle MLflow, règle simple de l'API — le site est inactif :
WARNING, ni verdict ni lancement. Le premier entraînement d'un site est une décision manuelle.

`services/ml/main.py` ne logge aujourd'hui que `mae` et `rmse` : c'est le repli qui joue. Le
calcul de `drift_threshold_mae` est une dépendance vers le lot ML, voir plus bas.

### Décision 3 — déclenchement sur dérive, filet hebdomadaire

Le déclencheur principal est la dérive : MAE 7 jours supérieure au seuil. Un filet
inconditionnel lance en plus un entraînement si le dernier date de plus de 7 jours : il couvre
une surveillance défaillante et une dérive lente restée sous le seuil.

Les deux se justifient l'un par l'autre : sans filet, tout repose sur une surveillance supposée
parfaite ; sans déclencheur, le filet réagit avec une semaine de retard. Dans les deux cas la
promotion reste conditionnelle : un réentraînement inutile ne coûte que du calcul, jamais une
régression.

### Décision 4 — verrou de 24 h, délai de grâce de 24 h

Réentraîner sert à donner au modèle des données du nouveau régime. Une heure après un
changement, le jeu d'entraînement ne contient qu'une heure du nouveau monde : le modèle
n'apprend rien et l'erreur reste haute. Il faut un cycle journalier complet — nuit, pic du
matin, creux de midi — pour qu'un réentraînement ait quelque chose de neuf à exploiter. D'où un
verrou : au plus un lancement par site et par 24 h, quelle qu'en soit la raison.

Même logique pour le verdict : pas de verdict tant que la fenêtre ne contient pas 24 h de
prédictions de la version en production.

La fenêtre est calée sur la semaine parce qu'il faut tous les types de jours pour juger ; le
verrou sur la journée parce qu'il faut un cycle complet pour apprendre.

## Ce que le superviseur ne fait pas

- **Il ne promeut jamais.** C'est le script d'entraînement qui compare et promeut.
- **Il n'entraîne pas un site qui n'a pas de modèle.** Le premier entraînement est une
  décision manuelle.
- **Il ne déclenche encore aucun entraînement.** Le lanceur en place, `LanceurJournal`,
  écrit `Lancement demande pour SITE00X (journal seulement, aucun entrainement declenche)`.
  Voir *Dépendances*.
- **Il ne garde pas d'état.** Le journal des lancements est en mémoire : après un
  redémarrage, le filet peut redemander un entraînement par site. Borné, assumé tant que le
  lanceur réel n'existe pas.
- **Il ne lit ni n'écrit rien d'autre** que `predictions` et `sites` en lecture, et son journal.

## Paramètres et défauts

Sept variables, préfixe `SUPERVISOR_`, lues par `app/supervisor/config.py`. Le détail est dans
`configuration.md`, section *Superviseur*.

| Variable | Défaut | Ce qu'elle règle |
|---|---|---|
| `SUPERVISOR_INTERVAL_SECONDS` | `300` | cadence des tours |
| `SUPERVISOR_DECISION_WINDOW_HOURS` | `168` | fenêtre de la MAE qui décide (décision 1) |
| `SUPERVISOR_ALERT_WINDOW_HOURS` | `24` | fenêtre de la MAE qui prévient (décision 1) |
| `SUPERVISOR_GRACE_HOURS` | `24` | données exigées avant tout verdict |
| `SUPERVISOR_LOCK_HOURS` | `24` | écart minimal entre deux lancements |
| `SUPERVISOR_MAX_MODEL_AGE_DAYS` | `7` | âge du filet (décision 3) |
| `SUPERVISOR_MAE_TOLERANCE` | `1.5` | seuil de repli = MAE holdout × tolérance (décision 2) |

Ce sont les valeurs des décisions ci-dessus, pas des valeurs calibrées sur des données réelles.
Elles sont configurables pour la démonstration, pas pour être changées en exploitation sans
revenir sur la décision.

## Provoquer une dérive pour la démo

Les données de la source sont stationnaires par construction : la dérive n'arrivera jamais
seule. Elle se provoque, avec les fenêtres et délais raccourcis par variables d'environnement,
et cela se dit explicitement au jury. La source expose pour cela
`POST /api/v1/simulate/spike/{site_id}?duration_minutes=N` (N de 1 à 240) : le site part en pic
de consommation pendant N minutes, les prédictions émises avant le pic se notent avec une erreur
forte. À défaut, un décalage injecté directement dans `predictions` fait le même travail
(levier 3 ci-dessous).

Préalable : un site dont les prédictions portent une `model_version` **présente dans le
registre MLflow**. Tant que l'API écrit `local-1` (règle simple), le superviseur journalise
`sans modele MLflow, supervision inactive` pour tous les sites et rien ne se déclenche.

Une fois ce préalable levé, trois leviers, du plus propre au plus rapide :

1. **Raccourcir les délais** dans le `.env` : `SUPERVISOR_GRACE_HOURS=1`,
   `SUPERVISOR_INTERVAL_SECONDS=30`, puis `docker compose up -d supervisor`.
2. **Abaisser le seuil** : `SUPERVISOR_MAE_TOLERANCE=0.1` fait passer n'importe quel modèle
   au-dessus de son seuil dès qu'il a 24 h de notes (ou une heure avec le levier 1).
3. **Injecter de l'erreur** : insérer dans `predictions` quelques lignes notées
   (`actual_kwh` renseigné) pour la version en production, avec un `predicted_kwh` très loin de
   la réalité, à des `target_at` dans les dernières 24 h. La MAE 24 h passe au-dessus du seuil
   → WARNING d'alerte au tour suivant ; la MAE 7 j suit → verdict `derive`.

Ce qu'on voit dans `docker compose logs -f supervisor` :

```
INFO app.supervisor.scheduler: Site SITE001 : MAE 7 j 12.000, MAE 24 h 13.000, seuil 10.000, verdict derive, dernier lancement jamais
INFO app.supervisor.lanceur: Lancement demande pour SITE001 (journal seulement, aucun entrainement declenche)
INFO app.supervisor.scheduler: Site SITE001 : entrainement demande (derive), version 3
```

Puis, au tour suivant, `verdict verrou, dernier lancement 2026-…` : la preuve que le verrou
tient.

## Dépendances vers les autres lots

**Lot API / prédiction** — *préalable à toute détection de dérive.*
`prediction_service.py` écrit aujourd'hui `model_version = "local-1"` (moyenne mobile), appelé
par deux processus : la boucle de prédiction de l'API et le conteneur `model`
(`services/backend/model/predict.py`), qui rejoue `refresh_stored_predictions` toutes les 60 s.
Le chargement du registre (`models:/<prefix>_<site>@production`) existait sur la branche `…/ML`
et a été retiré par `df09a3f`. Sans une version du registre dans `predictions.model_version`,
le superviseur n'a pas de seuil et reste inactif partout.

**Lot ML / entraînement** — *préalable au lanceur réel et au seuil de la décision 2.* Question
posée au propriétaire du ML, telle quelle :

> Exposer un point d'entrée machine (route interne sans CSRF, ou clé partagée en header) qui
> lance `main.py --site-id X --use-db` **avec** promotion, et faire précéder `register_alias`
> d'une comparaison de `mae` avec la version portant déjà l'alias `production` — ne promouvoir
> que si meilleure. Idéalement logger aussi `drift_threshold_mae` dans le run.

À quoi s'ajoute, depuis la décision 2 : `drift_threshold_mae` = pire MAE hebdomadaire des 2 mois
de test, augmentée de 20 %.

Ce qui existe et pourquoi ça ne suffit pas :

| Point d'entrée | Limite |
|---|---|
| `POST /training/api/jobs` (`services/ml/ui/training_ui.py`) | protégé pour le navigateur (`Origin` + CSRF) ; lance `main.py --no-production-alias` : la version produite n'atteint jamais la production |
| `python main.py` en CLI | autre conteneur, autre image, pas de socket Docker côté backend ; et `register_alias` promeut la dernière version **sans la comparer** à celle en place |
| `ML_TRAIN_ON_START` | une fois au démarrage du conteneur |

Quand ce point d'entrée existera, un second lanceur remplacera `LanceurJournal` dans
`__main__.py` sans toucher à l'ordonnanceur.

**Lot dashboard** — hors périmètre. L'écart prédiction / réalité est déjà stocké ; l'afficher
est du ressort du front.
