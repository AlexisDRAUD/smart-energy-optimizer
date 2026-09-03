"""Calcul des variables d entree du modele.

Importe par services/ml (entrainement) ET par services/backend (service).

Ne jamais dupliquer une de ces formules ailleurs. L entrainement et le service
calculeraient la meme variable de deux facons, le modele se degraderait en
production sans qu aucun test n echoue.

C est la seule raison d etre de ce paquet. Rien d autre n a vocation a y entrer :
ce dont un seul service se sert reste chez lui.
"""

from seo_features.features import (
    add_calendar_features,
    add_lag_features,
    build_feature_frame,
)

__all__ = ["add_calendar_features", "add_lag_features", "build_feature_frame"]
