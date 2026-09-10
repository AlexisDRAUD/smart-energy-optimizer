"""Worker de prevision.

Boucle longue qui rejoue les modeles MLflow et remplit la table ``predictions``.
A chaque passage, pour chaque site ``active`` :

1. lecture du dernier releve du site (``readings``) ;
2. prevision a l'horizon configure (``prediction_horizon_minutes``, 120 par
   defaut) par le modele versionne ``EnerVision_RF_Predictor_<site_id>`` (alias
   ``production``) charge depuis le registre MLflow via ``model/forecast.py``. Un
   site sans modele publie, ou un registre injoignable, est ignore : ce worker
   ne sert que des modeles MLflow, il n'a pas de repli local ;
3. ecriture d'une prevision (ignoree si une ligne identique existe deja) ;
4. rapprochement des previsions arrivees a echeance avec la mesure reelle.

L'orchestration (points 1 a 4) est dans ``model/refresh.py``, le service du
modele MLflow dans ``model/forecast.py``. Ce paquet ne depend que du registre
MLflow, des modeles ORM (``app.db``) et de la configuration ; il ne passe pas
par ``app.services``. Ce worker est le seul processus qui ecrit dans la table
``predictions`` ; la contrainte d'unicite ``site_id, target_at, model_version,
horizon_minutes`` protege quand meme les doublons.

Tourne dans son propre conteneur, a partir de l'image du backend, avec la
commande ``python -m model.predict``. La cadence vient de la boucle du processus,
pas d'un ordonnanceur externe (decision 26) ; ``SIGINT`` et ``SIGTERM`` arretent
le worker apres le passage en cours. Voir docker-compose.yml.

    python -m model.predict                       # boucle continue (60 s par defaut)
    python -m model.predict --once                # un seul passage (cron, test manuel)
    python -m model.predict --interval-seconds 300

Configuration : ``DATABASE_URL`` (obligatoire),
``PREDICTION_WORKER_INTERVAL_SECONDS`` (defaut 60),
``PREDICTION_HORIZON_MINUTES`` (defaut 120).
"""
