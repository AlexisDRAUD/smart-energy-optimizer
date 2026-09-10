# Modèle de prévision et pilotage

Livrable EC06 avec les scripts d'automatisation. Ce document couvre l'entraînement, la mise en
service, la surveillance et le réentraînement.

## Le problème

Prévoir la consommation d'un site deux heures à l'avance, à partir de son historique à la minute.
Le pas de temps de la source est la minute, l'horizon est de 120 minutes.

**Un modèle par site, pas un modèle global.** Les sites diffèrent par leur type et leur capacité, et
un modèle unique doit alors apprendre à la fois le comportement commun et les écarts entre sites.
La comparaison des deux stratégies a été faite avec `services/ml/compare_models.py`, et le choix
n'est donc pas une préférence.

## Les variables

Toutes calculées par `packages/features`, un paquet partagé installé aussi bien dans l'image
d'entraînement que dans l'image du backend. C'est le point le plus important de cette partie :
**l'entraînement et le service appellent le même code**, ce qui supprime par construction le
décalage entre les variables apprises et les variables servies.

Point d'entrée unique, `build_feature_frame(df)`, qui exige `measured_at` et `consumption_kwh`,
trie par site et par temps, puis ajoute :

| Variable | Définition |
|---|---|
| `hour`, `day_of_week`, `month` | extraites de l'horodatage UTC |
| `is_weekend` | 1 le samedi et le dimanche |
| `is_working_hours` | 1 entre 8 h et 18 h hors week-end |
| `lag_1`, `lag_60`, `lag_120` | consommation décalée de 1, 60 et 120 observations |
| `rolling_mean_30`, `rolling_mean_120` | moyennes glissantes sur 30 et 120 observations, calculées sur la série décalée d'un pas |
| `temperature_celsius`, `humidity_percent` | reprises telles quelles, converties en réel |

Deux précisions qui comptent. Les fenêtres sont exprimées **en nombre d'observations**, pas en
minutes : à une observation par minute les deux coïncident, mais un ré-échantillonnage changerait
leur sens. Et les moyennes glissantes portent sur la série décalée d'un pas, pour qu'une moyenne ne
contienne jamais la valeur qu'elle sert à prédire.

Le pipeline ajoute un encodage à chaud de `site_id` et `site_type`, et une imputation à zéro des
variables numériques manquantes. L'ordre et le type des colonnes attendues sont publiés avec le
modèle sous forme de **signature MLflow**, et vérifiés au chargement : le contrat d'entrée voyage
donc avec l'artefact, il n'est pas un document à côté.

## L'entraînement

`services/ml/main.py`, lancé dans le conteneur `mlflow`.

```bash
docker compose exec mlflow python /app/main.py            # tous les sites
docker compose exec mlflow python /app/main.py --site-id SITE001
```

Sans `--site-id`, le script regroupe les mesures par site et entraîne un modèle pour chacun, en
affichant sa progression.

**Source des données.** La table `readings` jointe au référentiel des sites, mesures nulles exclues.
Un fichier CSV peut être utilisé à la place avec `--csv`.

**Construction de la cible.** Chaque ligne reçoit la consommation réelle observée à
`measured_at + horizon`, par jointure stricte un pour un.

**Découpage temporel et garde anti-fuite.** Le jeu de test est la période la plus récente, deux mois
par défaut, et l'entraînement les vingt-deux mois qui précèdent. La condition qui compte est la
troisième : une ligne d'entraînement est retenue seulement si **sa cible aussi** est antérieure au
début de la période de test. Sans elle, une ligne du 30 juin prédisant le 1er juillet ferait entrer
une valeur de la période de test dans l'apprentissage.

**Modèle.** `RandomForestRegressor` par défaut, `ExtraTreesRegressor` en option, dans un pipeline
scikit-learn. Hyperparamètres par défaut : 150 arbres, profondeur maximale 15, graine 42.

**Métriques.** RMSE, MAE, et R² dès qu'il y a au moins deux lignes de test.

Trois mots sur leur lecture. La MAE dit de combien on se trompe en moyenne, dans l'unité de la
mesure. La RMSE pénalise davantage les grosses erreurs, et l'écart entre les deux révèle des
accidents ponctuels cachés derrière une moyenne rassurante. Le R² ne veut pas dire grand-chose seul
sur une série temporelle, où une prévision naïve obtient déjà un score élevé : c'est la comparaison
à une baseline qui tranche.

**Ce qui est enregistré dans MLflow**, un run par site : les paramètres, les métriques, le fichier
des prévisions de test, un graphique réel contre prédit, et le modèle avec sa signature.

**Registre.** Chaque modèle est enregistré sous `EnerVision_RF_Predictor_<site_id>` et reçoit
l'alias `production`. C'est cet alias que le service cherche.

Un verrou de fichier empêche deux entraînements simultanés.

## Où vivent le suivi et les artefacts

Le serveur MLflow tourne dans le conteneur `mlflow`, publié uniquement sur l'adresse locale de la
VM. Son magasin de suivi est un **SQLite** dans le volume `mlflow_data`. Les artefacts, modèles
compris, vont dans un seau S3 servi par **MinIO**, créé au démarrage par un conteneur
d'initialisation qui attend que le magasin réponde.

L'interface n'étant pas exposée, on y accède par un tunnel SSH :

```bash
ssh -L 5050:127.0.0.1:5000 root@10.138.200.30
# puis http://localhost:5050
```

C'est volontaire. Un serveur de suivi expose les métriques, les jeux de données et les artefacts, il
n'a rien à faire sur le réseau.

Le conteneur embarque aussi une page `/training` qui permet de lancer un entraînement par site
depuis le navigateur, avec contrôle d'origine et verrou partagé.

## La mise en service

Le conteneur `model` fait un passage toutes les soixante secondes.

Pour chaque site actif, il résout `EnerVision_RF_Predictor_<site>` par son alias `production`,
charge le modèle, prend les 240 derniers relevés, les passe à `build_feature_frame` et écrit la
prévision à deux heures. Le modèle chargé est mis en cache par version.

**Sans modèle dans le registre, il n'écrit rien.** Ni valeur approchée, ni repli statistique. Une
prévision affichée vient donc toujours d'un modèle nommé et versionné, et la table porte ce nom et
cette version à côté de chaque ligne.

Au début de chaque passage, il note aussi les prévisions arrivées à échéance : il cherche la mesure
réelle à l'horodatage visé et la rattache. L'erreur absolue est une colonne générée par PostgreSQL,
donc toujours cohérente avec les deux valeurs.

C'est ce mécanisme qui rend la surveillance possible : sans prévisions stockées et horodatées, aucune
mesure d'erreur en continu n'est calculable.

## L'alerte d'anticipation

Le même passage compare la prévision au dernier relevé réel et ramène l'écart à une **pente en
pourcentage par heure**, pour que le seuil reste comparable quel que soit l'horizon configuré :

```
pente = (prevu - reference) / reference * 100 * 60 / horizon_minutes
```

Au-delà de `PREDICTION_ALERT_RISE_PERCENT_PER_HOUR`, une alerte de type `forecast` est ouverte. La
sévérité suit le dépassement : `medium` au seuil, `high` au double, `critical` au triple.

Deux garde-fous, et ce sont eux qui font la différence entre une alerte utile et un bruit permanent.
Une référence inférieure à `PREDICTION_ALERT_MIN_BASELINE_KWH` ne déclenche rien, parce qu'à
quelques centaines de watts le moindre écart fait un pourcentage énorme. Et une alerte déjà ouverte
pour le même site au même instant n'est pas dupliquée, l'écriture se faisant dans la transaction du
passage.

C'est ce qui donne au modèle un usage métier. Une prévision qui n'entraîne aucune décision n'a pas
d'impact, et c'est la dernière question qu'un jury pose. Ici, elle signale une montée de charge deux
heures avant qu'elle ne soit constatée.

## Le pilotage

Le conteneur `supervisor` fait un tour toutes les cinq minutes et examine chaque site actif.

Il lit la table des prévisions et calcule la MAE glissante de la version en service, sur sept jours
pour décider et sur vingt-quatre heures pour alerter. Il va chercher le seuil dans MLflow : la
métrique `drift_threshold_mae` du run si elle existe, sinon la MAE d'entraînement multipliée par une
tolérance de 1,5.

Décisions possibles, dans l'ordre où elles sont évaluées :

| Décision | Signification |
|---|---|
| pas de version en service | rien à surveiller |
| pas de seuil | site non supervisé, avertissement |
| verrou | un lancement a déjà été demandé il y a moins de 24 h |
| filet | aucun réentraînement demandé depuis sept jours, sécurité périodique |
| grâce | moins de 24 h de notation, pas assez de recul |
| dérive | la MAE glissante dépasse le seuil |
| aucun | tout va bien |

**Le superviseur journalise sa décision et ne déclenche aucun entraînement.** C'est un choix, pas un
manque : une dérive détectée doit lever une alerte, pas remplacer un modèle toute seule. Le
lancement effectif viendra quand le service d'entraînement exposera un point d'entrée appelable par
une machine.

Deux limites à connaître : le journal des lancements est en mémoire et se perd au redémarrage du
conteneur, et aucune table ne trace les décisions, la trace est dans les journaux.

## Le réentraînement

**Politique annoncée** : un rythme hebdomadaire comme filet, un seuil pour réagir vite, et un
déclenchement manuel pour les changements connus à l'avance, arrivée d'un site ou changement d'usage.

**Le seuil à dire** : si la MAE glissante repasse au-dessus de la baseline de persistance, le modèle
n'apporte plus rien et doit être réentraîné.

Deux workflows portent l'automatisation :

- `.github/workflows/train.yml`, déclenché à la main, entraîne tous les sites sur le runner.
- `.github/workflows/mlflow_pipeline.yml`, déclenché à la main, à chaque push sur `main`, et par une
  tâche planifiée quotidienne à 02:00 UTC.

Garde-fous : ne jamais promouvoir sans comparer le nouveau modèle à l'ancien et à la baseline sur la
même période de test, conserver la version précédente pour pouvoir revenir en arrière, et ne pas
réentraîner sur une période anormale sans le savoir, ce que la table de qualité permet de vérifier
en amont.

## Comparaison des approches

`services/ml/compare_models.py` compare, sur un site et hors MLflow, une forêt aléatoire, une
régression Ridge et un modèle à gradient boosté quand la bibliothèque est disponible. Il produit un
tableau de métriques, les prévisions et des graphiques. C'est la matière du tableau comparatif des
choix technologiques.

## Ce qui n'est pas fait

- **La surveillance de la distribution des entrées** n'est pas branchée. Ce qui existe est la
  surveillance de la **sortie**, l'erreur réelle mesurée à échéance et comparée aux baselines de
  persistance et de régression linéaire par la route de performance du modèle. La distinction est à
  faire clairement : dérive des données, dérive du concept et dérive des prévisions ne se détectent
  ni ne se corrigent de la même façon.
- **Pas d'intervalle de prévision**, seulement une valeur. Une régression quantile donnerait un
  encadrement, ce qui change la décision d'un exploitant.
- **Pas de variable externe.** La météo est le premier facteur de consommation et n'est pas utilisée,
  faute de source ; le calendrier des jours fériés non plus.
- **Pas d'explication par prévision.** Sur un sujet énergie, savoir quel facteur a fait monter la
  prévision est ce qui permet d'agir.
- **Pas d'optimisation des hyperparamètres.** Les valeurs sont celles par défaut, choisies pour un
  temps d'entraînement raisonnable.
