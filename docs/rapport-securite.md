# Rapport de sécurité

Projet **EnerVision** (Smart Energy Optimizer). Version du 08/09/2026.

Ce rapport est le livrable de sécurité de l'épreuve Cloud. Il ne réécrit pas la documentation
technique, il l'assemble : `docs/security.md` porte le détail des contrôles et la remédiation des
scans, `docs/ci.md` fait foi sur la chaîne d'intégration, `infra/ansible/README.md` sur la
configuration de la machine. Ce document dit ce qu'on protège, contre quoi, avec quoi, et ce qu'on
a choisi de ne pas faire.

---

## 1. Périmètre et actifs à protéger

Le périmètre est la plateforme EnerVision déployée sur une VM du Proxmox de l'école : le dashboard,
l'API, la base PostgreSQL, la collecte, la transformation, le suivi de modèles et le magasin
d'artefacts. Le Proxmox lui-même n'est pas administré par l'équipe et sort du périmètre.

| Actif | Ce que c'est | Criticité | Pourquoi |
|---|---|---|---|
| Comptes utilisateurs | courriels et empreintes de mots de passe | **haute** | seule donnée personnelle du système, et la porte d'entrée |
| Clé de signature des jetons | `JWT_SECRET_KEY` | **haute** | qui l'obtient forge n'importe quelle session, sans mot de passe |
| Identifiants de la base | `POSTGRES_PASSWORD` | **haute** | accès complet aux données |
| Mesures de consommation | couches bronze, silver, gold | moyenne | non nominatives, mais c'est le produit, et leur perte coûte deux ans de reprise |
| Modèles et artefacts ML | MLflow et MinIO | moyenne | un artefact est désérialisé par `cloudpickle`, donc exécutable |
| Chaîne d'intégration | workflow, secrets de dépôt, registre | **haute** | qui la contrôle déploie ce qu'il veut sur la VM |
| Disponibilité du service | la VM et sa pile | moyenne | pas de contrainte contractuelle, mais la démonstration en dépend |

Le dépôt est public. Conséquence tirée dès le premier commit : rien de sensible n'y entre, parce
qu'un secret poussé une fois reste dans l'historique même après avoir été retiré du fichier.

---

## 2. Modèle de menace

| Surface | Menace | Impact | Parade en place |
|---|---|---|---|
| Formulaire de connexion | force brute, réutilisation de mots de passe | prise de compte | Argon2, jetons courts, rôles. **Pas de limitation de débit**, voir §10 |
| API | injection SQL | lecture ou destruction des données | ORM SQLAlchemy, requêtes paramétrées, aucune concaténation de chaîne dans une requête |
| API | entrées malformées | erreurs, comportements non prévus | validation Pydantic sur toutes les entrées et sorties |
| API | vol de jeton | usurpation de session | `access` d'une heure, `refresh` en cookie `httpOnly` limité au chemin d'authentification, champ `typ` vérifié |
| Front | XSS | vol de session | React échappe par défaut, le cookie de rafraîchissement est hors de portée du JavaScript |
| Base | accès direct depuis le réseau | fuite complète | port publié uniquement sur `127.0.0.1` de la VM, jamais sur son adresse réseau |
| Images et dépendances | CVE connue dans une base ou une bibliothèque | exécution de code | Trivy sur les trois images à chaque fusion, `CRITICAL` bloquant sur backend et web |
| Chaîne d'intégration | secret exfiltré par une PR | compromission du registre et de la VM | secrets non fournis aux PR issues de forks, permissions minimales par job, jeton éphémère |
| Accès à la machine | SSH forcé | contrôle de la VM | pas d'IP publique, pare-feu, clés SSH. **Mot de passe encore actif**, voir §10 |
| Artefacts ML | artefact malveillant désérialisé | exécution de code dans le backend | magasin interne, non exposé, artefacts produits par nos seuls entraînements |
| Réseau local | écoute du trafic | vol du cookie de session | **aucune**, le trafic est en clair, voir §10 |

---

## 3. Sécurité applicative

**Authentification.** Mots de passe hachés avec Argon2 via `pwdlib`. Aucune cryptographie écrite à
la main. Les jetons sont signés avec PyJWT : un jeton d'accès d'une heure présenté à chaque appel,
un jeton de rafraîchissement de sept jours qui ne sert qu'à le renouveler. Le second vit dans un
cookie `httpOnly`, limité au chemin `/api/v1/auth`, donc inaccessible au JavaScript de la page.

Les deux jetons portent un champ `typ`. Un jeton de rafraîchissement présenté en `Authorization`
est refusé. Sans cette vérification, il ouvrirait un accès de sept jours au lieu d'une heure.

**Contrôle d'accès.** Trois rôles, `viewer`, `operator`, `admin`, portés par le modèle utilisateur
et appliqués par une dépendance FastAPI `require_roles`. Le contrôle est donc déclaré route par
route et non laissé au front, qui ne fait que masquer ce qui n'est pas permis.

**Validation des entrées.** Pydantic sur l'ensemble des schémas, en entrée comme en sortie. Une
sortie validée évite aussi d'exposer par accident un champ qui n'a rien à faire dans une réponse.

**Injection SQL.** Les écritures et lectures passent par l'ORM. Là où du SQL est écrit à la main,
dans l'ETL et le collecteur, il est paramétré, les valeurs étant liées par nom et jamais insérées
dans la chaîne. Vérification faite sur l'ensemble du backend : aucune requête construite par
interpolation de chaîne.

**Origines croisées.** Aucune configuration CORS, et c'est délibéré. Le front et l'API sont servis
sur la même origine, le nginx du conteneur `web` relayant `/api/` vers l'API par le réseau interne
de Docker. Il n'y a donc pas de requête d'origine croisée à autoriser, ce qui supprime la classe de
mauvaises configurations qui commence par `allow_origins: ["*"]`.

**En-têtes de sécurité.** Absents aujourd'hui. Voir §10.

---

## 4. Gestion des secrets

Trois règles, appliquées partout : aucun secret dans le dépôt, ni dans le code, ni dans un fichier
de configuration versionné, ni dans une image, un `ENV` écrit dans un `Dockerfile` restant lisible
par `docker history`. Un fichier `.env.example` versionné porte les clés sans les valeurs. Les
secrets sont lus dans l'environnement au démarrage, jamais dans le code.

| Environnement | Où vit le secret |
|---|---|
| Poste de développement | `.env` ignoré par git, valeurs sans valeur réelle |
| Intégration continue | secrets de dépôt GitHub, injectés à l'exécution, masqués dans les journaux |
| Production | secret de dépôt `PROD_ENV` contenant le fichier entier, écrit sur la VM par le job de déploiement |

En production, le job écrit ce fichier avec `umask 077`, puisque le répertoire de travail du runner
est sur la machine, puis l'efface en fin de job même en cas d'échec, avec un `docker logout` du
registre au passage. Sur la machine, le fichier appartient au compte de service et porte les droits
`600`, donc lui seul peut le lire.

**Deux corrections du 08/09, à mentionner plutôt qu'à taire.** Le fichier compose fournissait des
valeurs par défaut pour dix variables sensibles : la pile démarrait donc sur `minioadmin` si une
valeur manquait. Ces défauts ont été remplacés par des variables obligatoires, la pile refuse
désormais de démarrer plutôt que de démarrer mal. Et `JWT_SECRET_KEY` valait `change_moi`,
c'est-à-dire la valeur par défaut publiée de `POSTGRES_PASSWORD` : la clé de signature des sessions
était devinable par quiconque lisait le dépôt. Tous les secrets concernés ont été changés, parce
qu'une valeur par défaut publiée reste valable tant qu'on ne la tourne pas.

**Un gestionnaire de secrets dédié a été étudié puis écarté.** Doppler apportait la rotation
centralisée et l'absence de fichier sur la machine, au prix d'un client à installer, d'un jeton à
gérer et d'une dépendance à la sortie internet de la VM. Pour une machine unique, le secret de
dépôt couvrait déjà le besoin. La limite est assumée : un seul secret global ne donne pas
d'historique par variable.

Le pre-commit comprend un contrôle `detect-private-key`. Un scanner de secrets complet, du type
gitleaks, n'est pas en place, voir §10.

---

## 5. Sécurité réseau et système

**Pas d'IP publique.** La VM est sur le réseau de l'école. Les utilisateurs sont l'équipe et les
évaluateurs, donc l'exposition à internet n'a aucune raison d'être, et la surface d'attaque depuis
internet est nulle.

**Un seul point d'entrée.** Le pare-feu ufw n'autorise que le 22 et le 80, tout le reste est refusé
en entrée. Le 443 est délibérément fermé tant qu'aucun frontal TLS n'écoute derrière : ouvrir un
port en prévision d'un service qui n'existe pas est un confort, pas un principe. Une variable
`enable_https` l'ouvrira le jour venu.

L'API, la base, MLflow et MinIO ne publient leurs ports que sur `127.0.0.1` de la VM. Le navigateur
ne parle qu'au port 80, et nginx relaie vers l'API par le réseau interne de Docker. Une seule règle
de pare-feu, un seul service joignable.

**Comptes.** L'application tourne sous un compte de service dédié, non root, membre du seul groupe
`docker`. L'accès administrateur se fait par SSH par clé. Le durcissement qui coupe
l'authentification par mot de passe est écrit dans le playbook et désactivé par défaut, pour ne pas
se fermer la porte de la machine avant d'avoir vérifié qu'une clé fonctionne. Voir §10.

**Exploitation.** Les journaux Docker sont plafonnés en taille et en nombre de fichiers, un disque
plein étant la panne la plus banale d'une machine qu'on administre soi-même. Le service Docker est
activé au démarrage et les conteneurs repartent seuls après un redémarrage machine.

**Rôles base de données.** Un seul rôle PostgreSQL aujourd'hui, propriétaire de tout. Le rôle
applicatif au moindre privilège est écrit dans le playbook mais désactivé par défaut. Voir §10.

---

## 6. Sécurité de la chaîne logicielle

Cette section est de la sécurité à part entière, pas du confort d'équipe.

**Le dépôt.** Le travail passe par des branches et des demandes de fusion relues. Personne ne
pousse directement sur la branche de livraison. Une revue obligatoire est le contrôle qui empêche
qu'une modification non vue arrive en production.

**La chaîne.** Sept jobs dans un fichier unique. Le style et le typage passent avant les tests, les
tests avant la construction des images, la construction avant le scan, le scan avant la publication,
la publication avant le déploiement. Chaque étape ne peut pas être sautée, puisque la suivante en
dépend.

**Analyse de vulnérabilités.** Trivy analyse les paquets système et les bibliothèques des trois
images, en `HIGH` et `CRITICAL`, vulnérabilités sans correctif comprises. Une `CRITICAL` sur le
backend ou le front fait échouer le contrôle, et le job de publication recharge exactement les
images scannées : **une image refusée ne peut donc pas être publiée**. Les rapports sont conservés
trente jours comme artefacts, ils constituent l'annexe factuelle de ce rapport. L'image MLflow est
scannée et son rapport publié sans bloquer, arbitrage motivé au §10.

**Intégrité de la chaîne elle-même.** L'action Trivy est épinglée par empreinte de commit et non par
étiquette, une étiquette pouvant être redéplacée sur un autre code. Les permissions sont déclarées
au plus juste par job, seul le job de publication obtenant l'écriture sur le registre. Le
déploiement s'authentifie avec le jeton de l'exécution, qui expire à la fin du job : aucun jeton
personnel durable ne vit sur la machine.

**Traçabilité.** Chaque image porte deux étiquettes, l'empreinte du commit, immuable, et le nom de
la branche, mobile. Comme une étiquette mobile ne dit pas quel commit tourne, les images portent un
label OCI de révision : un `docker inspect` rend l'empreinte exacte du code en service. C'est aussi
ce qui rend le retour arrière possible, en remettant l'empreinte voulue et en redéployant.

**Dépendances.** Versions bornées côté Python, `npm ci` sur fichier de verrouillage côté front. Pas
de mise à jour automatisée des dépendances, voir §10.

---

## 7. Journalisation et détection

La supervision applicative existante tient le rôle de détection. La table `etl_runs` trace chaque
exécution de transformation avec sa fenêtre et son résultat, `data_quality_daily` porte les
indicateurs de qualité par jour, l'état des capteurs signale les sources muettes. Un trou de
collecte, une transformation qui échoue en boucle ou une source qui ne répond plus se voient donc
sans avoir à ouvrir les journaux.

**Ce qu'on ne journalise jamais**, et c'est la partie qui compte : aucun mot de passe, aucun jeton,
aucun contenu de cookie, aucun en-tête `Authorization`. Une trace d'authentification enregistre le
résultat et l'identifiant du compte, jamais la valeur présentée. Côté déploiement, les tâches
Ansible qui manipulent un secret sont marquées `no_log`, et le SQL portant un mot de passe passe par
un fichier en droits `600` plutôt que par la ligne de commande, un argument de commande étant
lisible dans `ps` et dans les journaux du système.

Il n'y a pas de collecte centralisée des journaux ni d'alerte automatique. Voir §10.

---

## 8. Sauvegarde et reprise

Une tâche planifiée quotidienne produit un dump compressé de la base, avec rotation par ancienneté.
Le script écrit d'abord un fichier temporaire et ne le renomme qu'en cas de succès, donc un fichier
portant le nom final est toujours un fichier complet. Il commence par `set -euo pipefail`, ce qui
évite le cas classique du dump qui échoue pendant que la compression réussit et fait passer
l'ensemble pour un succès.

Un script de restauration existe, il arrête les services applicatifs, injecte l'archive et les
relance. Une restauration est toujours un acte délibéré : rien ne restaure automatiquement au
démarrage, ce qui écraserait une base saine au moindre redémarrage.

Deux limites, l'une et l'autre au §10 : la restauration n'a pas encore été jouée, et les
sauvegardes vivent sur le disque de la machine qu'elles protègent.

En cas de perte totale de la VM, la reprise repose sur le playbook, qui reconstruit la machine et
redéploie, puis sur la reprise d'historique depuis l'API source, qui reconstitue les données brutes.

---

## 9. Données personnelles

La seule donnée personnelle traitée est le compte utilisateur : une adresse de courriel, une
empreinte de mot de passe Argon2, un rôle et un état d'activation. Aucun nom, aucune adresse, aucune
donnée de localisation, aucun traceur analytique, aucun appel à un service tiers depuis le front.

Les mesures de consommation portent sur des sites et non sur des personnes. Elles ne sont pas des
données à caractère personnel en l'état. La nuance à garder pour un usage réel : une courbe de
consommation à la minute sur un site occupé par une seule personne devient une donnée de
comportement, donc un déploiement chez un client résidentiel changerait cette qualification.

Les comptes existants sont ceux de l'équipe et des évaluateurs. Le mot de passe n'est jamais stocké
ni journalisé en clair, et il n'existe aucun mécanisme d'export en masse des comptes.

---

## 10. Risques acceptés

Un rapport de sécurité sans risque résiduel n'est pas crédible : il signifie qu'on n'a pas cherché,
ou qu'on cache.

| Risque | Pourquoi il est accepté aujourd'hui | Échéance |
|---|---|---|
| **Pas de HTTPS.** Le cookie de session circule en clair sur le réseau de l'école, `COOKIE_SECURE` est donc à `false` | Réseau fermé, pas d'IP publique, et un frontal TLS demande un certificat que le contexte scolaire ne fournit pas simplement | Frontal TLS et bascule du cookie, avant tout usage réel |
| **Sudo sans mot de passe pour le compte de déploiement.** Ce compte est de fait administrateur de la machine | Le playbook installe des paquets et écrit dans `/etc`, et personne n'est devant le clavier pour saisir un mot de passe. La VM n'héberge que cette application et le runner est limité à ce dépôt | Restreindre à un ensemble de commandes si la machine venait à héberger autre chose |
| **Authentification SSH par mot de passe encore active** | Couper le mot de passe avant d'avoir vérifié qu'une clé fonctionne ferme la porte d'une machine dont nous n'avons pas la console | Dès la première connexion par clé confirmée. La bascule est déjà écrite dans le playbook |
| **Un seul rôle PostgreSQL**, propriétaire de tout. La règle « la couche brute est en insertion seule » est tenue par le code, pas par les droits | Basculer demande deux URL de connexion distinctes, une pour les migrations et une pour l'API. Modification à faire sciemment, pas la veille d'une livraison | Rôle applicatif au moindre privilège, déjà écrit et désactivé |
| **Pas de limitation de débit** sur le formulaire de connexion | Surface limitée au réseau de l'école, pas d'exposition internet | Avant toute exposition publique |
| **Pas de révocation de session.** Un jeton de rafraîchissement copié reste valable jusqu'à expiration | Demande une table de sessions et un contrôle à chaque renouvellement | À traiter avec la table de sessions |
| **Pas d'en-têtes de sécurité** sur le frontal | Le front est servi en même origine et sans script tiers, ce qui limite l'exposition réelle | À ajouter avec le frontal TLS, la politique de contenu en premier |
| **Sauvegardes sur le disque qu'elles protègent** | Elles couvrent l'erreur humaine et la corruption, pas la perte de la machine | Copie hors machine, même manuelle et hebdomadaire |
| **Restauration jamais éprouvée** | Le script existe pour que l'essai tienne en une commande, l'essai n'a pas encore été fait | Un essai complet, à dater et à consigner |
| **Scan MLflow non bloquant** | Le serveur n'écoute que sur l'adresse locale, et sa pile scientifique remonte des vulnérabilités sans correctif disponible | Rendre bloquant une fois le premier rapport lu et les exceptions écrites |
| **Pas de détection de secrets dans l'historique** au-delà du contrôle de clé privée | Le pre-commit couvre le cas le plus courant, et la règle « aucun secret dans le dépôt » est tenue par la revue | Ajouter un scanner dédié dans la chaîne |
| **Pas de mise à jour automatisée des dépendances** | Les versions sont bornées et les images rescannées à chaque fusion | Activer une mise à jour automatisée après la livraison |
| **Pas de collecte centralisée des journaux ni d'alerte** | La supervision applicative couvre les pannes qui comptent pour ce produit | Supervision technique si le produit passe en exploitation réelle |

---

## 11. Confrontation au dossier de conception

Le dossier de conception annonçait une sécurité pensée dès la conception. Ce rapport en est la
vérification, et l'exercice n'a d'intérêt que s'il dit aussi ce qui n'a pas été tenu.

**Tenu.** Aucun secret dans le dépôt, du premier commit à aujourd'hui. Hachage par une bibliothèque
standard, jamais de cryptographie maison. Jetons courts et typés, cookie hors de portée du
JavaScript. Moindre privilège réseau, un seul port ouvert et aucun service interne joignable.
Analyse de vulnérabilités bloquante intégrée à la chaîne, et non ajoutée après coup. Compte de
service non root. Sauvegarde et restauration décrites en code.

**Non tenu à ce jour.** Le chiffrement du transport, le moindre privilège au niveau de la base, la
révocation de session et la limitation de débit. Trois de ces quatre points sont déjà écrits et
désactivés par un interrupteur : ce n'est pas de l'intention, c'est du travail fait qu'on n'a pas
activé, et la différence se vérifie dans le dépôt.

**Ce que l'exercice a révélé.** La revue du 08/09 a trouvé une clé de signature de session qui
valait une valeur par défaut publiée. Le contrôle qui a manqué n'est pas un outil, c'est l'absence
de règle interdisant les valeurs par défaut sur les variables sensibles. La correction porte donc
sur la cause et non sur le symptôme : ces variables sont désormais obligatoires, et la pile refuse
de démarrer si l'une manque.

---

## Annexes

- Rapports Trivy des trois images, artefacts de la chaîne d'intégration, conservés trente jours.
- `docs/security.md` : détail des contrôles et remédiation datée des rapports du 08/09/2026.
- `docs/ci.md` : chaîne d'intégration, permissions et politique de publication, fait foi.
- `infra/ansible/` : configuration de la machine et déploiement, en code.
- `docs/runbook.md` : exploitation, dont sauvegarde et restauration.
