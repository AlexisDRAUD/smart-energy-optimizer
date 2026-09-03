"""ETL.

Lit la couche brute, controle, repare, agrege, ecrit la couche transformee
(readings). Tourne toutes les minutes sur une fenetre glissante de trente
minutes, et peut etre rejoue sur une fenetre deja traitee sans creer de doublon.

Tourne dans son propre conteneur, a partir de l image du backend, avec la
commande `python -m app.etl`. Voir docker-compose.yml.

N y va pas : le calcul des variables d entree du modele, il est dans
packages/features pour que l entrainement et le service partagent la formule.
"""
