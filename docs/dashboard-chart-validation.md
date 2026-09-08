# Validation du graphique — étape 1

## Périmètre

Route `/api/v1/consumption-chart`, dashboard et contrats uniquement. Aucun LTTB,
changement de modèle, imputation, agrégation métier, migration ou écriture en base.
La carte « Dernier écart évalué » affiche la dernière paire native comparable dans
la période choisie. Son pourcentage est évalué à la lecture ; les scores historiques
stockés et les métriques du modèle ne sont pas réécrits.

## Tests automatisés

Résultats locaux du 7 septembre 2026 : **94 tests backend réussis** sur PostgreSQL
16.4 isolé, **33 tests frontend réussis**. TypeScript (application et tests), ESLint,
build Vite, Ruff et contrôle de formatage réussis. Les dépendances émettent des
avertissements de dépréciation non bloquants (Starlette/AnyIO et `punycode`).

Vérification complémentaire dans Chrome avec des réponses API synthétiques :
24 h, 7 jours, 30 jours, ruptures conservées, aucune erreur JavaScript ni débordement
horizontal à 1440 et 390 pixels. Cette vérification visuelle ne remplace pas la
validation du déploiement et des données réelles sur la VM.

Frontend, depuis `services/web` :

```sh
npm ci
npm run typecheck
npm run typecheck:test
npm run lint
npm test -- --runInBand
npm run build
```

Backend, depuis `services/backend`, avec les dépendances de `requirements.txt` :

```sh
python -m pytest tests -o addopts= --tb=short -q
```

Configurer explicitement `DATABASE_URL` et `TEST_DATABASE_URL` avant pytest.
La base de test doit être distincte de la base applicative, son nom doit finir par
`_test` et le compte doit pouvoir la recréer. La fixture **supprime et recrée la base
de test**, jamais la base applicative. Sans configuration de test, les tests PostgreSQL
sont ignorés : ce résultat ne valide pas le backend.

Depuis la racine, avec Ruff 0.16.5 :

```sh
python -m ruff check .
python -m ruff format --check .
```

## Vérifications fonctionnelles sur la VM après déploiement manuel

1. Mettre à jour backend et frontend ensemble. La route apparaît dans `/docs`.
   Aucune migration n'est nécessaire. Vérifier que `LOCAL_MODEL_NAME` et
   `LOCAL_MODEL_VERSION` désignent bien le modèle de production actuellement écrit
   par le service ; le graphique sélectionne toujours l'horizon 120 minutes.
2. Ouvrir le dashboard avec un compte viewer. Dans l'onglet Réseau, vérifier un
   appel `/consumption-chart` avec le bon site, `start`, `end`, sans `limit` ni
   `offset`. Vérifier les trois périodes et leurs durées exactes en UTC.
3. Vérifier que les valeurs natives restent à la même échelle sur les trois vues.
   Les maxima ne doivent plus être multipliés par 15 ou 60 à cause des sommes.
   Le maximum peut toutefois varier si la période contient d'autres mesures.
4. Avec seulement une journée disponible, vérifier que les 7/30 jours ne sont pas
   étirés artificiellement : axe complet et couverture faible sont visibles.
   Une période vide conserve ses bornes et affiche l'absence de données.
5. Vérifier que les prédictions historiques disponibles apparaissent sur toutes
   les vues, dans l'ordre, sans trait partant du dernier réel. Un seul point doit
   rester visible. Le graphique futur a les bornes `[end, end + 2 h[` et n'étend
   pas le graphique historique. Sans cible future, il indique l'absence de valeur.
6. Vérifier les ruptures autour des minutes absentes et des valeurs nulles sur un
   jeu de test comportant ces situations. Vérifier les compteurs de couverture.
   Ne pas injecter de données de test dans la base de production.
7. Pour « Dernier écart évalué », retrouver `last_evaluated.target_at` dans les
   mesures et prédictions de la réponse : site et timestamp doivent correspondre
   exactement, avec version de production/H+2. Vérifier date, version et horizon
   sur la carte. Sans paire : indisponible ; prédit zéro : métadonnées conservées,
   pourcentage indisponible. Changer de période peut changer cette dernière paire.
8. Faire un appel authentifié de plus de 30 jours, puis un appel avec `limit=500` :
   attendre 422 explicite. Site inconnu : 404. Sans authentification : 401.
   Un dépassement du plafond de volume est testé automatiquement ; ne pas le
   provoquer en remplissant la base de production. Expiration SQL : 503 explicite.
9. Changer rapidement de site/période pendant un chargement : une ancienne réponse
   ne doit pas remplacer la sélection courante. Vérifier aussi un écran étroit.

## Validation du volume et des performances

- Sur une série continue complète, vérifier que `downsampling.*.output_points` vaut
  600 pour 24 heures, 7 jours et 30 jours, et que les premier et dernier points natifs
  sont présents.
- Sur une série contenant des valeurs nulles ou des intervalles absents, vérifier que
  chaque null et les deux bords de chaque rupture restent présents. Le résultat peut
  dépasser 600 points lorsque ces points obligatoires épuisent le budget.
- Le test unitaire traite 43 200 points continus puis 43 200 points alternant valeur et
  null. Sa limite de deux secondes protège contre une régression importante tout en
  restant volontairement large pour les environnements CI.
- La performance HTTP sur 30 jours doit être mesurée avec `TEST_DATABASE_URL` sur une
  base PostgreSQL dédiée : le temps inclut alors les lectures SQL, les calculs complets,
  LTTB et la sérialisation. Une exécution ignorée faute de base n'est pas une validation.

## Limites à conserver visibles

- kWh est l'unité déclarée par la source. La durée physique d'intégration reste
  inconnue ; aucune conversion en kW ou normalisation par 60 n'a été faite.
- Les comptes actifs ont accès à tous les sites selon la politique actuelle.
  Cette étape ne crée pas de gestion de droits par site.
- La route peut lire jusqu'à 43 201 mesures et 43 321 prédictions pour ses calculs
  complets. L'affichage vise ensuite 600 points par série avec LTTB. Un délai SQL de
  5 secondes et les plafonds fixes protègent la lecture ; aucune troncature silencieuse.
  Une série très fragmentée peut dépasser la cible pour conserver tous ses points obligatoires.
- L'historique de prévisions absent en base n'est pas reconstruit. Si la version
  de production n'a pas encore de prévisions, ses séries restent vides.
- Les routes historiques d'agrégats et les autres pages restent inchangées.

LTTB est actif côté serveur sur les séries destinées à l'affichage uniquement.
