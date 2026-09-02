# Tests

## Couverture visée

| Zone                   | Cible | Pourquoi                                  |
|------------------------|---|-------------------------------------------|
| Pipeline de donnees    | environ 80 % des branches | c'est la que se cache la perte de données |
| API, inférence, règles | environ 70 % | contrat exposé                            |
| Dashboard              | pas de seuil | le risque n'est pas la                    |

Un seuil unique pousse a ecrire des tests inutiles sur le code d'affichage pour atteindre un
chiffre.

## Familles de tests

- **Unitaires.** Calcul des variables d'entrée, règles d'imputation, règles de
  recommandation, calcul des seuils.
- **Integration.** Le collecteur écrit bien dans la couche brute, le job de transformation
  est rejouable sans créer de doublon, l'API rend bien ce que le contrat annonce.
- **Qualité des donnees.** Contrôles sur les valeurs et les plages. **Ils ne bloquent pas le
  pipeline**, ils marquent l'anomalie. Bloquer transformerait un problème de qualité en perte
  de données.
- **Resilience.** Injection de pannes : source injoignable, base indisponible, conteneur
  arrêté.
- **Non fonctionnels.** Temps de réponse de l'API sur une fenêtre longue, temps du job de
  transformation.

## Lancer les tests

```bash
TODO: à complété
```
