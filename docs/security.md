# Sécurité

## Le dépôt est public

Conséquence directe : rien de sensible dans le dépôt, dès le premier commit. Un secret pousse
une fois reste dans l'historique meme apres avoir été retire du fichier.

| Categorie | Exemples                                                                      | Ou ca vit                        |
|---|-------------------------------------------------------------------------------|----------------------------------|
| Secret | mot de passe base, cle de signature des jetons, destination du canal d'alerte | `.env` local et secrets du dépôt |
| Pas un secret mais jamais en dur | adresse de l'API source, adresse de la VM                                     | variables d'environnement        |
| Public | schémas, documentation, code                                                  | le dépôt                         |

`.env.example` liste les noms de variables avec des valeurs factices. Il est versionné.
`.env` ne l'est jamais.

## Surface d'attaque

1. L'API exposée sur internet.
2. Le formulaire de connexion.
3. La base de donnees.
4. Les images de conteneurs et leurs dépendances.
5. La chaine d'intégration et ses secrets.
6. Les dépendances tierces du front.
7. Le code généré par des assistants, relu comme le reste.

## Contrôles

- Mots de passe haches par une bibliothèque standard. Aucune cryptographie écrite a la main.
- Jetons signes a durée de vie courte : une heure pour l'access token présenté a chaque
  appel, sept jours pour le refresh token qui ne sert qu'a le renouveler.
- Le refresh token vit dans un cookie `httpOnly`, hors de portée du JavaScript, limité au
  chemin `/api/v1/auth` et marqué `Secure` en production (`COOKIE_SECURE=true`). Un XSS sur
  le dashboard ne permet donc pas de prolonger une session au dela de l'heure en cours.
- Les deux jetons portent un champ `typ`. Un refresh token présenté en `Authorization` est
  refusé : sans cette vérification il ouvrirait un accès de sept jours.
- Dépendances figées par version.
- Analyse des images et des dépendances dans la chaine d'intégration avec Trivy ; les
  vulnérabilités critiques bloquent leur publication.
- Aucun identifiant durable stocké côté client au dela du jeton.

## Scan des images

Trivy analyse les images backend et web à chaque demande de fusion vers `main` ou `dev`, puis à
chaque envoi vers `dev`. Une vulnérabilité `CRITICAL` fait échouer le contrôle et empêche toute
publication ; une `HIGH` est rapportée sans bloquer.

**La politique complète, les artefacts et les permissions sont décrits dans `ci.md`**, qui fait
foi sur ce point.

### Limites

Trivy détecte ce qui est présent dans sa base de vulnérabilités au moment du
run. Ce contrôle d'image ne remplace pas un test dynamique de l'API ou du site,
une analyse des erreurs de logique métier, un test d'intrusion, ni la surveillance
de l'environnement en exécution. Une nouvelle CVE publiée après le build ne sera
visible qu'au prochain scan ; les images doivent donc être reconstruites et
analysées régulièrement.

### Remédiation des rapports du 8 septembre 2026

Le backend utilise `mlflow-skinny==3.16.0`, aligné sur le MLflow complet du
service d'entraînement. Il conserve le chargement `pyfunc` des modèles
scikit-learn/cloudpickle et les clients d'artefacts HTTP et S3, avec leurs
dépendances scientifiques et `boto3` explicites. La version de scikit-learn
est identique dans les deux services pour les modèles sérialisés. Le backend
ne lance pas de serveur MLflow ; ses prévisions actuelles restent le calcul
local de `prediction_service.py`.

Cette version dépasse les versions corrigées indiquées pour les CVE MLflow
du rapport qui disposent d'un correctif. Le paquet complet et sa dépendance
`pyarrow` ne sont plus installés dans le backend. Skinny contient encore du
code MLflow partagé : ce changement n'est pas une preuve que toute CVE sans
correctif a disparu. En particulier, CVE-2026-0545 concerne les endpoints de
jobs du serveur, non exposés par le backend. Ne pas activer l'exécution de
jobs du serveur d'entraînement sans réévaluer cet avis. Ne charger que des
artefacts de confiance : cloudpickle peut exécuter du code à la désérialisation.

Le runtime web exige `libuuid>=2.42.3-r1`, version corrigée pour les sept
alertes HIGH du premier rapport Alpine.

Le backend utilise désormais **Ubuntu 24.04 LTS**, avec les mises à jour des
dépôts officiels et Python 3.12 fourni par Ubuntu, dans un environnement
virtuel. Cette base conserve glibc et les wheels scientifiques ARM64 sans
introduire de paquets Debian testing/unstable.

Contrairement à Debian trixie/bookworm, Ubuntu noble fournit les correctifs
des trois alertes CRITICAL `perl-base` :

| CVE | Version Ubuntu corrigée |
| --- | --- |
| [CVE-2026-13221](https://ubuntu.com/security/CVE-2026-13221) | `5.38.2-3.2ubuntu0.4` |
| [CVE-2026-42496](https://ubuntu.com/security/CVE-2026-42496) | `5.38.2-3.2ubuntu0.3` |
| [CVE-2026-8376](https://ubuntu.com/security/CVE-2026-8376) | `5.38.2-3.2ubuntu0.3` |

Le build vérifie que `perl-base` est au moins en `5.38.2-3.2ubuntu0.4`.
Le paquet essentiel et les métadonnées du gestionnaire de paquets restent
présents : il s'agit de correctifs distribués par Ubuntu, pas d'une exclusion
du scan. Aucune exception Trivy ni modification des seuils CI n'est appliquée.
Reconstruire régulièrement avec `--pull` pour intégrer les mises à jour.

Validation locale ARM64 du 8 septembre 2026 avec Trivy 0.74.0 (OS et
bibliothèques, vulnérabilités sans correctif incluses) : les rapports fournis
contenaient 3 CRITICAL et 51 HIGH côté backend, zéro côté web ; les deux
images reconstruites ont **zéro HIGH et zéro CRITICAL**. `pip check`, les deux
tests MLflow (chargement scikit-learn/pyfunc, artefacts HTTP et client S3) et
43 tests unitaires backend passent ; huit tests PostgreSQL sont ignorés en
l'absence de base de test dédiée. Ces résultats ne remplacent pas le scan CI
de l'architecture publiée.

## Ce qui n'est pas fait

Écrit ici plutôt que passé sous silence : une limite assumée vaut mieux qu'une affirmation
fausse.

- **Un seul rôle PostgreSQL.** Le projet n'utilise que le rôle `seo`, propriétaire de tout.
  L'objectif reste le moindre privilège : un rôle qui écrit le brut sans `UPDATE` ni `DELETE`,
  un rôle en lecture seule pour l'API et pour le ML. Aujourd'hui la règle « la couche brute est
  en insertion seule » est tenue par le code, **pas par les droits**.
- **Pas de révocation de session.** `logout` efface le cookie du navigateur, mais un refresh
  token copié ailleurs reste valable jusqu'à son expiration. Il faudrait une table de sessions
  en base.
- **Pas de HTTPS**, ni en local ni sur la VM. `COOKIE_SECURE` reste donc à `false`, et le
  cookie de session circule en clair sur le réseau de l'école.
- **Pas de limitation de débit** sur le formulaire de connexion.
