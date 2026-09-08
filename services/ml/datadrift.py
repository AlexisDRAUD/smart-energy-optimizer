import numpy as np
from scipy.stats import ks_2samp

# Référence : données utilisées à l'entraînement

reference = np.random.normal(loc=15, scale=5, size=500)  # ex: température moyenne 15°C

# Actuel : nouvelles données de production (ex: la semaine dernière)

current = np.random.normal(loc=22, scale=4, size=200)  # un été plus chaud

# Test statistique : les deux échantillons viennent-ils de la même distribution ?

stat, p_value = ks_2samp(reference, current)

THRESHOLD = 0.05

if p_value < THRESHOLD:
    print(f"⚠️ Drift détecté (p_value={p_value:.4f}) — la distribution a changé")

else:
    print(f"OK, pas de drift significatif (p_value={p_value:.4f})")
