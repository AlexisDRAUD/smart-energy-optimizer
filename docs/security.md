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

- Roles au moindre privilege dans la base. Le role qui écrit le brut n'a ni `UPDATE` ni
  `DELETE`. Le role qui lit pour l'API n'écrit pas.
- Mots de passe haches par une bibliothèque standard. Aucune cryptographie écrite a la main.
- Jetons signes a durée de vie courte : une heure pour l'access token présenté a chaque
  appel, sept jours pour le refresh token qui ne sert qu'a le renouveler.
- Le refresh token vit dans un cookie `httpOnly`, hors de portée du JavaScript, limité au
  chemin `/api/v1/auth` et marqué `Secure` en production (`COOKIE_SECURE=true`). Un XSS sur
  le dashboard ne permet donc pas de prolonger une session au dela de l'heure en cours.
- Les deux jetons portent un champ `typ`. Un refresh token présenté en `Authorization` est
  refusé : sans cette vérification il ouvrirait un accès de sept jours.
- Reste a faire : la révocation. `logout` efface le cookie du navigateur, mais un refresh
  token copié ailleurs reste valable jusqu'a son expiration. Il faudrait une table de
  sessions en base pour le couper vraiment.
- Dépendances figées par version.
- Analyse des images et des dépendances dans la chaine d'intégration avec Trivy ; les
  vulnérabilités critiques bloquent leur publication.
- Aucun identifiant durable stocké côté client au dela du jeton.

## Scan des images avec Trivy

La chaine construit et analyse les images backend et web sur chaque pull request
vers `main` ou `dev`, puis de nouveau sur chaque push vers `dev`. Le scan couvre
les vulnérabilités connues des paquets du système d'exploitation et des
bibliothèques applicatives, pour les niveaux `HIGH` et `CRITICAL`.

La politique est la suivante :

- `HIGH` : visible dans les logs, le résumé du job et le rapport JSON, sans
  bloquer la chaine ;
- `CRITICAL` : échec du contrôle et aucune publication dans GHCR ;
- vulnérabilité sans correctif : elle reste rapportée et applique la même
  politique ;
- aucune exception ou règle `.trivyignore` n'est appliquée par défaut.

Les rapports `backend.json` et `web.json` sont conservés 30 jours dans
l'artefact `trivy-image-reports-<sha>` du run GitHub Actions. Ils constituent la
trace détaillée du contrôle. Le résumé du job fournit les nombres de
vulnérabilités et les logs donnent notamment l'identifiant CVE, le paquet, les
versions installée et corrigée, et la cible concernée.

Le job exécuté sur les pull requests possède uniquement `contents: read`. Il ne
référence aucun secret du dépôt, ne demande pas `packages: write` et utilise
l'événement `pull_request`, qui ne transmet pas les secrets du dépôt aux forks.
La connexion GHCR et `packages: write` sont isolés dans le job de publication,
conditionné à un push vers `dev` après la réussite du scan.

### Limites

Trivy détecte ce qui est présent dans sa base de vulnérabilités au moment du
run. Ce contrôle d'image ne remplace pas un test dynamique de l'API ou du site,
une analyse des erreurs de logique métier, un test d'intrusion, ni la surveillance
de l'environnement en exécution. Une nouvelle CVE publiée après le build ne sera
visible qu'au prochain scan ; les images doivent donc être reconstruites et
analysées régulièrement.
