"""Worker de prevision.

Boucle longue qui rejoue le modele et remplit la table ``predictions``. A chaque
passage, pour chaque site ``active`` :

1. lecture du dernier releve du site (``readings``) ;
2. prevision a l'horizon configure (``prediction_horizon_minutes``, 120 par
   defaut) : moyenne des 24 derniers releves, modele ``local-moving-average``.
   Cette branche n'a pas d'integration MLflow, le modele entraine de
   ``services/ml`` n'est pas encore branche ici ;
3. ecriture d'une prevision (ignoree si une ligne identique existe deja) ;
4. rapprochement des previsions arrivees a echeance avec la mesure reelle.

Le calcul est celui de ``app.services.prediction_service``, partage avec l'API.
Celle-ci lance deja la meme boucle en interne toutes les
``prediction_refresh_interval_seconds`` (60 s) ; ce worker sort cette charge du
conteneur API sur la meme cadence par defaut. Les deux ecritures sont idempotentes
(contrainte d'unicite ``site_id, target_at, model_version, horizon_minutes``).

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
