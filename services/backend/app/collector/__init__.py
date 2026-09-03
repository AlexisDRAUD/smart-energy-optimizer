"""Collecteur.

Interroge la source toutes les minutes et ecrit la reponse telle quelle dans la
couche brute (raw_readings, raw_snapshots). N interprete rien : ce qui est jete
ici est perdu definitivement.

Tourne dans son propre conteneur, a partir de l image du backend, avec la
commande `python -m app.collector`. Voir docker-compose.yml.

N y va pas : la moindre transformation, elle est dans app/etl/.
"""
