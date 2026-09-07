"""Superviseur ML.

Surveille, site par site, l erreur du modele en production et declenche son
reentrainement quand elle derive ou quand le filet hebdomadaire l impose. Ne
promeut jamais un modele : c est le script d entrainement qui compare et promeut.

Deux responsabilites, deux modules, un processus :
- monitoring.py : mesurer. Lit `predictions`, deja notee par l API, et rend la
  MAE par site sur la fenetre de decision et sur la fenetre d alerte.
- scheduler.py : decider et lancer. Compare au seuil du modele, applique le
  verrou et le filet, appelle le lanceur d entrainement injecte.

Tourne dans son propre conteneur, a partir de l image du backend, avec la
commande `python -m app.supervisor`. Voir docker-compose.yml.
"""
