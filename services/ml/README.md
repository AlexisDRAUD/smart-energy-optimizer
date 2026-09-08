# Service ML

`docker compose up -d --build mlflow` attend PostgreSQL, les migrations et
l'initialisation bornee du bucket MinIO, puis lance **un seul conteneur** :
serveur MLflow et entrainement depuis `readings` joint a `sites`.

Un modele `EnerVision_RF_Predictor_<site_id>` est versionne pour chaque site
disposant d'assez de donnees ; son alias `production` est mis a jour apres
evaluation et publication. Aucun modele entraine est une erreur.

## Configuration

- `ML_TRAIN_ON_START=1` : entrainer a chaque demarrage (nouvelle version).
  Mettre `0` pour servir uniquement, notamment sur une base vide.
- `TRAIN_ARGS=--holdout-minutes 120` : valeur Compose pour les 24 heures de
  demonstration. Pour un historique reel :
  `--train-months 22 --holdout-months 2 --min-train-rows 500`.
- `MLFLOW_START_TIMEOUT_SECONDS=120` : attente HTTP bornee.
- `DATABASE_URL` : fourni par Compose ; obligatoire hors Docker.

Le script sans argument utilise PostgreSQL. `--csv /chemin/fichier.csv` est un
choix explicite, jamais un repli automatique. Les CSV ne sont pas dans l'image.
Le champ `consumption_kwh` est prioritaire si `consumption_kw` existe aussi.

L'horizon est aligne sur l'horodatage exact (120 minutes par defaut), et non
sur un nombre de lignes. Les cibles traversant la limite du holdout sont purgees.
Le package commun `seo_features` calcule les variables pour entrainer et servir.
Seules les variables calendrier, retards, meteo et categories sont utilisees ;
les horodatages, cibles et colonnes brutes supplementaires sont exclus.
Les retards historiques du package restent exprimes en nombre d'observations.
Le backend sert actuellement des previsions a 120 minutes : conserver cet
horizon pour les modeles auxquels il accede.

## Exploitation

Interface : http://127.0.0.1:5000.

### Entraîner depuis MLflow

Cliquer **Entraîner un modèle** dans MLflow (ou ouvrir
http://127.0.0.1:5000/training). Choisir le site PostgreSQL, Random Forest ou
Extra Trees, et la durée du holdout puis **Entraîner**. La requête retourne
immédiatement ; le processus travaille dans le même conteneur. Un verrou
interprocessus empêche les entraînements simultanés (UI, CLI et démarrage).
Les jobs et leurs runs enfants sont persistés dans MLflow ; les jobs interrompus
sont signalés lors du prochain affichage.

Les runs enfants affichent **MAE**, **RMSE** (kWh, plus bas est meilleur) et
**R²** (plus haut est meilleur, peut être négatif ; absent pour un seul exemple).
Il s'agit de régression, pas d'une « accuracy » de classification.
Dans les artefacts du run : `holdout/predictions.csv` contient toutes les valeurs
réelles/prédites et horodatages ; `holdout/actual_vs_predicted.png` les compare.
Le graphe peut être sous-échantillonné pour rester lisible, jamais le CSV.

**L'UI ne promeut pas automatiquement le modèle.** Dans **Models**, ouvrir la
version évaluée et lui attribuer explicitement l'alias `production`.
La CLI et le démarrage gardent leur comportement existant ; utiliser
`--no-production-alias` pour empêcher leur promotion automatique.
`ML_TRAIN_ON_START=0` permet un fonctionnement entièrement manuel.

L'intégration utilise le point d'extension serveur officiel `mlflow.app`
(`--app-name enervision`) de **MLflow 3.16.0**, version épinglée et vérifiée.
La factory étend les routes Flask puis utilise `create_fastapi_app` fourni par
cette version de MLflow pour les servir avec son serveur Uvicorn par défaut :
les routes natives ASGI, le proxy d'artefacts et la sécurité MLflow sont conservés.
Les hôtes autorisés sont localhost, 127.0.0.1 et le service Compose `mlflow` ;
adapter explicitement cette liste dans `start.py` pour un domaine de déploiement.
Les modèles conservent la sérialisation CloudPickle utilisée par les clients MLflow 2.
C'est une extension EnerVision, pas l'interface native Databricks ni un plugin
frontend officiel : seul le HTML d'accueil reçoit un lien de navigation, sans
modifier les bundles JavaScript. La page et les API sont des routes Flask du
même serveur, port et origine ; aucun serveur ni conteneur supplémentaire.
Les POST imposent origine identique et jeton CSRF. Cela ne remplace pas
l'authentification : conserver la liaison localhost ou protéger tout le serveur
par une passerelle authentifiée avant exposition réseau.

```bash
# Nouvelle version, sans redemarrer le serveur ni creer un autre conteneur
docker compose exec mlflow python main.py --holdout-minutes 120
docker compose logs mlflow
```

Une erreur d'entrainement au démarrage arrete le conteneur avec un code non nul (pas de boucle
de redemarrage automatique). SIGTERM/SIGINT sont transmis aux groupes de
processus ; l'arret de MLflow interrompt aussi l'entrainement.
Une erreur d'un job manuel est enregistrée comme `FAILED` sans arrêter MLflow ;
les détails techniques restent dans les logs du conteneur.

SQLite est persiste dans `mlflow_data` a `/mlflow/mlflow.db`. Les artefacts sont
dans le bucket `mlflow-artifacts` du volume `minio_data`. MLflow sert de proxy
HTTP : l'API et les clients n'ont besoin que de `MLFLOW_TRACKING_URI`, pas des
identifiants MinIO. Les ports sont limites a localhost.

Les anciens experiments utilisant une URI `s3://` ne sont pas convertis par
un changement de configuration serveur. Creer un nouvel experiment avec
`--experiment <nouveau-nom>` pour publier avec le proxy ; conserver les anciens
volumes et migrer leurs artefacts separement si necessaire.
Un ancien SQLite relatif situe hors volume n'est pas migre automatiquement.
