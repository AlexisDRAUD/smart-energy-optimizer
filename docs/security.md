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
- Analyse des images et des dépendances dans la chaine d'intégration, résultats traités et
  non ignorés.
- Aucun identifiant durable stocké côté client au dela du jeton.
