# ADR-2026-09-04 — Stratégie d’imputation de la consommation

- Statut : **activé en production le 2026-09-07**
- Date : 2026-09-04, activation le 2026-09-07

> Les sections « Contexte », « Décision », « Traçabilité » et « Conséquences » décrivent l'état
> du 2026-09-04, quand la stratégie était retenue mais pas branchée. Elles sont conservées telles
> quelles pour la traçabilité. **Ce qui vaut aujourd'hui est décrit dans « Activation du
> 2026-09-07 », en fin de document**, y compris pour `SITE004` et `SITE007`.

## Contexte

Les historiques de consommation peuvent contenir de courtes séquences sans valeur exploitable.
Avant d’intégrer une méthode d’imputation à l’ETL, nous devons comparer hors production deux
candidates simples, indépendamment pour chaque site : le report de la dernière valeur réelle et
l’interpolation linéaire entre les valeurs réelles qui entourent la séquence manquante.

Les historiques de `SITE004` et `SITE007` sont confirmés comme invalides. Ils sont donc exclus de
la décision actuelle. Cette exclusion est documentaire : leurs identifiants ne doivent pas être
codés en dur dans l’algorithme générique et leurs données ne doivent pas être supprimées. Aucune
règle d’imputation de production ne doit être activée pour ces sites.

## Décision

Le choix est évalué par `services/backend/app/analysis/imputation_backtest.py`. Ce composant reste
strictement expérimental : il ne modifie aucune donnée, n’écrit pas en base et n’active aucune
imputation dans l’ETL de production.

Le backtest masque artificiellement toutes les fenêtres valides de 1, 2 et 3 minutes. Chaque
fenêtre possède une valeur réelle avant la séquence, les valeurs masquées, puis une valeur réelle
après la séquence. La cadence attendue est exactement d’une minute. Une valeur nulle, une
observation portant la raison `network_loss`, une valeur non finie ou une rupture de cadence coupe
la série ; aucune fenêtre ne traverse une telle coupure.

Les seuils provisoires et configurables sont :

| Paramètre | Valeur | Signification |
|---|---:|---|
| `minimum_points` | 100 | Nombre minimal de valeurs masquées évaluées |
| `minimum_method_improvement` | 0,10 | Gain relatif minimal de l’interpolation, soit 10 % |
| `maximum_normalized_error` | 0,10 | Erreur normalisée maximale acceptable, soit 10 % |
| `maximum_gap_minutes` | 3 | Durée maximale d’une fenêtre testée |

Les deux seuils à 10 % expriment des notions différentes et conservent donc des noms distincts.

Pour chaque site, la MAE et la consommation maximale utilisent la même unité. Les métriques sont
calculées comme suit :

```text
normalized_mae_linear_pct =
    mae_linear / max_observed_consumption * 100

normalized_mae_report_pct =
    mae_report / max_observed_consumption * 100

relative_improvement_pct =
    (mae_report - mae_linear) / mae_report * 100
```

Une division par zéro ne produit pas de valeur arbitraire : la métrique concernée est indéfinie et
le profil reste `unknown` si elle est nécessaire à la décision. Les erreurs et l’amélioration
relative calculables sont conservées même lorsque le nombre de points est insuffisant.

La classification retenue est :

- données insuffisantes ou métriques invalides : `unknown` ;
- interpolation meilleure d’au moins `minimum_method_improvement` et MAE linéaire normalisée au
  plus égale à `maximum_normalized_error` : `variable` ;
- sinon, si la MAE du report normalisée reste au plus égale à
  `maximum_normalized_error` : `stable` ;
- aucune méthode candidate assez précise : `unknown`.

Chaque résultat conserve `sample_count`, `sequence_count`, `max_observed_consumption`, les deux
MAE, les deux MAE normalisées, l’amélioration relative, le `profile` et `decision_reason`. Cette
dernière valeur rend explicite la règle qui a conduit à la classification.

## Traçabilité et usage ML

Les règles suivantes sont validées pour une future intégration, qui reste hors du périmètre de cet
ADR expérimental :

- une valeur imputée pourra être utilisée comme entrée d’un modèle ML ;
- elle devra conserver `is_imputed=true` et renseigner `imputation_method` ;
- elle ne devra pas devenir une cible présentée comme réelle pour l’entraînement ou l’évaluation
  sans validation explicite des équipes Data/ML ;
- `consumption_kwh_raw` ne devra jamais être écrasée.

## Conséquences

La décision est reproductible et explicable par site, mais elle ne vaut pas encore règle de
production. Les seuils restent provisoires et devront être validés sur un historique fiable avant
toute connexion à l’ETL. Le traitement à appliquer à `SITE004` et `SITE007` demeure suspendu à la
mise à disposition ou à la validation d’un historique exploitable.

*Paragraphe dépassé depuis le 2026-09-07 : la validation a eu lieu, voir la section suivante.*

## Activation du 2026-09-07

La condition posée par cet ADR était : « les seuils restent provisoires et devront être validés
sur un historique fiable avant toute connexion à l'ETL ». Elle est levée.

Le backtest a été rejoué sur sept jours de mesures réelles reprises depuis l'API de la source,
soit 70 560 lignes, et non sur les CSV. Résultat :

| Site | Profil | Points testés | MAE linéaire % | MAE report % | Gain % |
|---|---|---:|---:|---:|---:|
| SITE001 | variable | 46 891 | 2,46 | 2,81 | 12,31 |
| SITE002 | variable | 45 878 | 2,64 | 2,99 | 11,53 |
| SITE003 | variable | 46 700 | 4,09 | 4,60 | 11,17 |
| SITE004 | variable | 46 746 | 3,03 | 3,44 | 11,94 |
| SITE005 | variable | 45 708 | 4,01 | 4,55 | 11,79 |
| SITE006 | variable | 46 612 | 2,48 | 2,82 | 11,96 |
| SITE007 | variable | 46 593 | 2,70 | 3,08 | 12,19 |

Chaque site dépasse largement les 100 points requis, reste sous les 10 % d'erreur normalisée et
gagne plus de 10 % avec l'interpolation. Les sept sites sont donc classés `variable`, et la
méthode retenue est l'interpolation linéaire.

### Sur l'exclusion de SITE004 et SITE007

Cet ADR les excluait, leurs historiques étant confirmés invalides. Cette exclusion portait sur
les CSV de 2023-2024, que le projet n'utilise pas. Sur l'historique de l'API, ces deux sites se
classent comme les cinq autres, avec 46 746 et 46 593 points testés.

Ils sont donc traités comme les autres, sans qu'aucun identifiant de site figure dans le code,
conformément à cet ADR. La protection reste en place et reste générique : un site dont les
données se dégradent sort `unknown` au recalcul suivant et **cesse aussitôt d'être imputé**.

### Ce qui a été branché

Le profil de chaque site est rangé dans `sites.imputation_profile` et recalculé toutes les
24 heures par l'ETL. La réparation tourne à chaque passage, sur les 30 dernières minutes de
`readings`.

Les trois règles de sûreté sont tenues par le code, pas par convention :

- le calcul part de `consumption_kwh_raw`, jamais de `consumption_kwh` ;
- l'écriture porte `WHERE consumption_kwh_raw IS NULL`, donc une valeur réelle n'est jamais
  écrasée ;
- un trou ouvert, qui touche l'instant présent, n'est pas comblé.

Mesure de contrôle sur les sept jours repris : **4 173 valeurs nulles réparées sur 4 176**. Les
trois restantes sont les mesures les plus récentes de la base, des trous encore ouverts. Rejouer
la réparation ne modifie plus aucune ligne et n'en recompte aucune.
