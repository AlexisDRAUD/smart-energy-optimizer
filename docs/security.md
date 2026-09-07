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
