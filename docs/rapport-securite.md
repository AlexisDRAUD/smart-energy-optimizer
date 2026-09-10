# Rapport de sécurisation

Projet **EnerVision** (Smart Energy Optimizer). Livrable EC04. Version du 10/09/2026.

Ce rapport dit ce qui est protégé, contre quoi, avec quoi, et ce qui a été délibérément laissé de
côté. Chaque affirmation est vérifiable dans le dépôt ou par une commande donnée en annexe.

Il ne réécrit pas la documentation technique : `ci.md` fait foi sur la chaîne d'intégration,
`deploiement.md` sur la machine, `api-contract.md` sur les routes.

---

## 1. Périmètre et actifs

Le périmètre est la plateforme déployée sur une VM du Proxmox de l'école, `10.138.200.30` : le
dashboard, l'API, PostgreSQL, la collecte, la transformation, le suivi de modèles et le magasin
d'artefacts. Le Proxmox n'est pas administré par l'équipe et sort du périmètre.

| Actif | Criticité | Pourquoi |
|---|---|---|
| Comptes utilisateurs, courriel et empreinte du mot de passe | **haute** | seule donnée personnelle, et la porte d'entrée |
| Clé de signature des jetons | **haute** | qui l'obtient forge une session sans mot de passe |
| Identifiants de la base | **haute** | accès complet aux données |
| Secret de dépôt `PROD_ENV` | **haute** | contient tous les secrets de production |
| Mesures de consommation | moyenne | non nominatives, mais leur perte coûte deux ans de reprise |
| Modèles et artefacts | moyenne | un artefact est désérialisé par `cloudpickle`, donc exécutable |
| Chaîne d'intégration | **haute** | qui la contrôle déploie ce qu'il veut sur la VM |

**Le dépôt est public.** Conséquence tirée dès le premier commit : aucun secret n'y entre, parce
qu'un secret poussé une fois reste dans l'historique même après avoir été retiré du fichier.

---

## 2. Modèle de menace

| Surface | Menace | Impact | Parade |
|---|---|---|---|
| Formulaire de connexion | force brute, réutilisation de mots de passe | prise de compte | Argon2, jetons courts, rôles. **Pas de limitation de débit**, §9 |
| API | injection SQL | lecture ou destruction des données | ORM, requêtes paramétrées, aucune concaténation. Vérifié, §3 |
| API | entrées malformées | comportements non prévus | Pydantic en entrée et en sortie, `extra="forbid"`, bornes sur tous les paramètres |
| API | vol de jeton | usurpation de session | accès d'une heure, rafraîchissement en cookie `httpOnly` limité au chemin d'authentification, champ `typ` vérifié |
| Front | XSS | vol de session | React échappe par défaut, le cookie de rafraîchissement est hors de portée du JavaScript |
| Base | accès direct depuis le réseau | fuite complète | port publié uniquement sur la boucle locale de la VM |
| Images et dépendances | CVE connue | exécution de code | Trivy sur les trois images à chaque fusion, `CRITICAL` bloquant sur backend et web |
| Chaîne d'intégration | secret exfiltré par une PR | compromission du registre et de la VM | permissions minimales par job, jeton éphémère, secrets non fournis aux forks |
| Chaîne d'intégration | dérive entre code livré et code en service | démonstration ou production d'une version non voulue | labels OCI de révision. **Aucun contrôle automatique**, §9 |
| Accès à la machine | SSH forcé | contrôle de la VM | pas d'IP publique, pare-feu. **Mot de passe root encore actif**, §9 |
| Réseau local | écoute du trafic | vol du cookie de session | **aucune**, le trafic est en clair, §9 |

---

## 3. Sécurité applicative

**Authentification.** Mots de passe hachés avec Argon2 via `pwdlib`. Aucune cryptographie écrite à
la main. Jetons signés en HS256 avec PyJWT : un jeton d'accès d'une heure présenté à chaque appel,
un jeton de rafraîchissement de sept jours qui ne sert qu'à le renouveler.

Le second vit dans un cookie nommé `enervision_refresh_token`, `httpOnly`, `SameSite=Lax`, limité au
chemin `/api/v1/auth`, et marqué `Secure` dès que `COOKIE_SECURE` passe à `true`. Il est renouvelé à
chaque connexion et à chaque rafraîchissement, et supprimé à la déconnexion.

Les deux jetons portent un champ `typ` vérifié au décodage. Un jeton de rafraîchissement présenté en
`Authorization` est refusé : sans cette vérification, il ouvrirait un accès de sept jours au lieu
d'une heure.

**Contrôle d'accès.** Trois rôles, `viewer`, `operator`, `admin`, appliqués route par route par une
dépendance FastAPI. La gestion des comptes est réservée aux administrateurs, l'acquittement des
alertes aux opérateurs et aux administrateurs. La liste des rôles est verrouillée à trois endroits :
contrainte de vérification en base, type littéral dans les schémas, et dépendance dans les routes.

**Validation des entrées.** Pydantic sur l'ensemble des schémas, en entrée comme en sortie, avec
refus des champs inconnus. Tous les paramètres de pagination sont bornés, la fenêtre du graphique
est plafonnée à trente jours et une échéance future est refusée. Une sortie validée évite aussi
d'exposer par accident un champ qui n'a rien à faire dans une réponse.

**Injection SQL.** Les écritures et lectures passent par l'ORM. Là où du SQL est écrit à la main,
dans l'ETL, le collecteur et le service du graphique, les chaînes sont des littéraux et les valeurs
sont liées par paramètres nommés. **Vérification effectuée sur l'ensemble du backend : aucune
requête construite par concaténation ni par interpolation de chaîne.** La commande de vérification
est en annexe.

**Épuisement de ressources.** La route du graphique pose un délai maximal d'exécution de cinq
secondes sur sa transaction et rend une erreur explicite au-delà, plutôt que de laisser une requête
lourde monopoliser la base.

**Origines croisées.** Aucune configuration CORS, et c'est délibéré : le front et l'API sont servis
sur la même origine, nginx relayant `/api/` par le réseau interne de Docker. Il n'y a donc pas de
requête d'origine croisée à autoriser, ce qui supprime la classe de mauvaises configurations qui
commence par une origine à `*`.

**En-têtes de sécurité.** Absents, §9.

---

## 4. Gestion des secrets

Trois règles, appliquées partout : aucun secret dans le dépôt, ni dans le code, ni dans un fichier
de configuration versionné, ni dans une image, un `ENV` écrit dans un `Dockerfile` restant lisible
par `docker history`. Un fichier `.env.example` versionné porte les noms de variables sans valeurs.
Les secrets sont lus dans l'environnement au démarrage, jamais dans le code.

| Environnement | Où vit le secret |
|---|---|
| Poste de développement | `.env` ignoré par git, valeurs sans valeur réelle |
| Intégration continue | secrets de dépôt GitHub, injectés à l'exécution, masqués dans les journaux |
| Production | secret de dépôt `PROD_ENV`, contenant le fichier entier |

En production, le job de déploiement écrit ce fichier avec `umask 077`, puisque le répertoire de
travail du runner est sur la VM, puis l'efface en fin de job **même en cas d'échec**, avec une
déconnexion du registre au passage. Sur la machine, le fichier appartient au compte de service et
porte les droits `600`.

Le compose rend cinq variables **obligatoires** par la syntaxe `${VAR:?message}` :
`POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `SEED_USER_PASSWORD`, `MINIO_ROOT_USER` et
`MINIO_ROOT_PASSWORD`. La pile refuse de démarrer si l'une manque, au lieu de démarrer sur une
valeur par défaut.

### Deux incidents, et ce qu'ils ont changé

Ils sont rapportés ici parce qu'ils sont la partie utile de ce rapport.

**08/09, valeurs par défaut publiées.** Le fichier compose fournissait des valeurs par défaut pour
dix variables sensibles : la pile démarrait donc sur les identifiants d'usine du magasin d'objets si
une valeur manquait. Et `JWT_SECRET_KEY` valait `change_moi`, c'est-à-dire la valeur par défaut
publiée de `POSTGRES_PASSWORD` : la clé de signature des sessions était devinable par quiconque
lisait le dépôt. Correction : ces variables sont devenues obligatoires, et tous les secrets
concernés ont été changés, parce qu'une valeur par défaut publiée reste valable tant qu'on ne la
tourne pas.

**09/09, secrets recopiés dans le fichier d'exemple.** Quatre secrets réellement générés se sont
retrouvés dans `.env.example`, donc dans un dépôt public, identiques à ceux du poste de
développement. Correction : repères explicites dans le fichier d'exemple, rotation des quatre
valeurs, et resserrement du `.gitignore` sur `.env*` après qu'un fichier de sauvegarde d'environnement
eut échappé au motif précédent. **La production n'a jamais partagé ces valeurs**, ses secrets ayant
été générés séparément.

**Ce que ces deux incidents ont en commun est la conclusion à retenir.** Le contrôle qui manque
n'est pas une règle, elle existait et était écrite, c'est une **détection automatique**. Un secret se
propage par copier-coller entre fichiers, et aucun humain ne rattrape ça de façon fiable. La suite
logique est un scanner de secrets dans la chaîne, §9.

**Ce qui a été étudié puis écarté.** Un gestionnaire de secrets dédié apportait la rotation
centralisée et l'absence de fichier sur la machine, au prix d'un client à installer, d'un jeton à
gérer et d'une dépendance à la sortie internet de la VM. Pour une machine unique, le secret de dépôt
couvrait déjà le besoin. La limite est assumée : un seul secret global ne donne pas d'historique par
variable.

---

## 5. Sécurité réseau et système

**Pas d'IP publique.** La VM est sur le réseau de l'école. Les utilisateurs sont l'équipe et les
évaluateurs, donc l'exposition à internet n'a aucune raison d'être, et la surface d'attaque depuis
internet est nulle.

**Deux ports ouverts, pas trois.** Le pare-feu ufw n'autorise que le 22 et le port du dashboard,
tout le reste est refusé en entrée. Le 443 est **fermé** tant qu'aucun frontal TLS n'écoute derrière,
et le playbook comporte une tâche qui retire la règle si elle existait : ouvrir un port en prévision
d'un service qui n'existe pas est un confort, pas un principe.

**Un seul service joignable.** L'API, la base, MLflow et MinIO ne publient leurs ports que sur la
boucle locale de la VM. Le navigateur ne parle qu'au port 80, et nginx relaie vers l'API par le
réseau interne de Docker. L'accès administrateur à MLflow se fait par tunnel SSH, sans ouvrir de
port.

**Comptes.** Trois identités séparées, décrites dans `deploiement.md` : `root` pour l'administration,
`deploy` pour le runner, `enervision` pour l'application. Le compte de service ne se connecte pas et
n'appartient qu'au groupe `docker`.

**Exploitation.** Journaux Docker plafonnés en taille et en nombre, service Docker activé au
démarrage, conteneurs en redémarrage automatique.

**Rôles base de données.** Un seul rôle PostgreSQL aujourd'hui, propriétaire de tout. Le rôle
applicatif au moindre privilège est écrit dans le playbook, avec révocation de la création sur le
schéma public et aucun droit de structure, mais il est désactivé par défaut, §9.

---

## 6. Sécurité de la chaîne logicielle

Cette section est de la sécurité à part entière, pas du confort d'équipe.

**Le dépôt.** Le travail passe par des branches et des demandes de fusion relues. Une revue
obligatoire est le contrôle qui empêche qu'une modification non vue arrive en production.

**La chaîne.** Sept jobs enchaînés, chacun dépendant du précédent : style et typage, tests,
construction, scan, publication, déploiement. Aucune étape ne peut être sautée.

**Analyse de vulnérabilités.** Trivy analyse les paquets système et les bibliothèques des trois
images, en `HIGH` et `CRITICAL`, vulnérabilités sans correctif comprises. Une `CRITICAL` sur le
backend ou le front fait échouer le contrôle, et le job de publication recharge **exactement** les
images scannées : une image refusée ne peut pas être publiée. Les rapports sont conservés trente
jours et constituent l'annexe factuelle de ce rapport.

**Intégrité de la chaîne.** L'action de scan est épinglée par empreinte de commit et non par
étiquette, une étiquette pouvant être redéplacée sur un autre code. Les permissions sont déclarées
au plus juste par job, seul le job de publication obtenant l'écriture sur le registre. Le
déploiement s'authentifie avec le jeton de l'exécution, qui expire à la fin du job : aucun jeton
personnel durable ne vit sur la machine.

**Traçabilité.** Chaque image porte deux étiquettes, l'empreinte du commit et le nom de la branche,
plus deux labels OCI dont la révision. Un `docker inspect` rend donc l'empreinte exacte du code en
service, ce qui rend le retour arrière possible et vérifiable.

**Incident du 09/09, à connaître.** Un déploiement a mis à jour la configuration sans mettre à jour
les images, parce que la commande de tirage respectait une politique qui saute les images déjà
présentes. La configuration décrivait alors un service que le code livré ne contenait pas. Le défaut
est corrigé, mais la leçon est ailleurs : **le déploiement affichait un succès alors que le code
n'avait pas bougé**. Rien ne vérifiait son effet. Le contrôle manquant est en §9.

**Dépendances.** Versions bornées côté Python, installation sur fichier de verrouillage côté front.
Pas de mise à jour automatisée, §9.

---

## 7. Journalisation et détection

La supervision applicative tient le rôle de détection. `etl_runs` trace chaque passage de
transformation avec sa fenêtre et son résultat, `data_quality_daily` porte la complétude par jour,
l'état des capteurs signale les sources muettes, et la table des prévisions porte l'erreur réelle
mesurée à échéance. Un trou de collecte, une transformation qui échoue en boucle ou un modèle qui
dérive se voient sans ouvrir un journal.

**Ce qu'on ne journalise jamais**, et c'est la partie qui compte : aucun mot de passe, aucun jeton,
aucun contenu de cookie, aucun en-tête d'autorisation. Une trace d'authentification enregistre le
résultat et le compte, jamais la valeur présentée.

Côté déploiement, les tâches Ansible qui manipulent un secret sont marquées `no_log`, et le SQL
portant un mot de passe passe par un fichier en droits `600` puis effacé, plutôt que par la ligne de
commande : un argument de commande est lisible dans la liste des processus et dans les journaux du
système.

Pas de collecte centralisée ni d'alerte automatique, §9.

---

## 8. Sauvegarde, reprise et données personnelles

**Sauvegarde.** Tâche planifiée quotidienne, `pg_dump` compressé écrit sous un nom temporaire et
renommé seulement en cas de succès, échec explicite si l'archive est vide, rotation par ancienneté.
Le script commence par `set -euo pipefail`, ce qui évite le cas classique du dump qui échoue pendant
que la compression réussit et fait passer l'ensemble pour un succès.

**Restauration.** Script dédié, confirmation demandée, arrêt des services applicatifs le temps de
l'opération. Rien ne restaure automatiquement au démarrage, ce qui écraserait une base saine au
moindre redémarrage.

**Reprise après perte de la machine.** Le playbook reconstruit et redéploie, puis la reprise
d'historique reconstitue les données brutes depuis la source.

**Données personnelles.** La seule donnée personnelle traitée est le compte utilisateur : une adresse
de courriel, une empreinte Argon2, un rôle et un état d'activation. Aucun nom, aucune adresse, aucune
donnée de localisation, aucun traceur, aucun appel à un service tiers depuis le front.

Les mesures portent sur des sites et non sur des personnes, elles ne sont donc pas des données à
caractère personnel en l'état. La nuance à garder pour un usage réel : une courbe de consommation à
la minute sur un site occupé par une seule personne devient une donnée de comportement, et un
déploiement chez un client résidentiel changerait cette qualification.

---

## 9. Risques acceptés

Un rapport de sécurité sans risque résiduel n'est pas crédible : il signifie qu'on n'a pas cherché,
ou qu'on cache.

| Risque | Pourquoi accepté aujourd'hui | Échéance |
|---|---|---|
| **Pas de HTTPS**, le cookie de session circule en clair | réseau fermé, pas d'IP publique, certificat non fourni par le contexte | frontal TLS et bascule du cookie, avant tout usage réel |
| **Pas d'en-têtes de sécurité** sur le frontal | front en même origine, sans script tiers | à ajouter avec le frontal TLS, la politique de contenu en premier |
| **Sudo sans mot de passe pour le compte de déploiement** | le playbook écrit dans `/etc` et personne n'est devant le clavier. La VM n'héberge que cette application et le runner est limité à ce dépôt | restreindre à un ensemble de commandes si la machine héberge autre chose |
| **Authentification SSH par mot de passe encore active, en `root`** | c'est le seul accès fourni par l'école, et la console de secours n'est pas accessible | dès qu'un compte non root joignable par clé est confirmé |
| **Un seul rôle PostgreSQL** | basculer demande deux URL de connexion distinctes, à faire sciemment | rôle applicatif déjà écrit, à activer |
| **Pas de limitation de débit** sur la connexion | surface limitée au réseau de l'école | avant toute exposition publique |
| **Pas de révocation de session** | un jeton de rafraîchissement copié reste valable jusqu'à expiration | table de sessions |
| **Sauvegardes sur le disque qu'elles protègent** | couvrent l'erreur humaine et la corruption, pas la perte de la machine | copie hors machine, même hebdomadaire |
| **Restauration jamais éprouvée** | le script existe pour que l'essai tienne en une commande | un essai daté et consigné |
| **Le déploiement ne vérifie pas son effet** | découvert le 09/09, corrigé à la source mais sans garde-fou | comparer le label de révision de l'image en service au commit déployé, et faire échouer le job sinon |
| **Scan MLflow non bloquant** | serveur en écoute locale, pile scientifique aux vulnérabilités sans correctif | rendre bloquant après lecture du premier rapport |
| **Pas de détection de secrets** au-delà du refus de clé privée en pre-commit | la règle est tenue par la revue, ce qui a échoué deux fois | scanner dédié dans la chaîne |
| **Pas de mise à jour automatisée des dépendances** | versions bornées, images rescannées à chaque fusion | à activer après la livraison |
| **Pas de collecte centralisée des journaux ni d'alerte** | la supervision applicative couvre les pannes qui comptent | supervision technique si passage en exploitation réelle |

---

## 10. Confrontation au dossier de conception

Le dossier de conception annonçait une sécurité pensée dès la conception. Cette section vérifie ce
qui a été tenu, et l'exercice n'a d'intérêt que s'il dit aussi ce qui ne l'a pas été.

**Tenu.** Aucun secret dans le dépôt à ce jour, et deux écarts détectés et corrigés en cours de
route. Hachage par une bibliothèque standard. Jetons courts et typés, cookie hors de portée du
JavaScript. Moindre privilège réseau, un seul port ouvert et aucun service interne joignable.
Analyse de vulnérabilités bloquante intégrée à la chaîne et non ajoutée après coup. Compte de
service non root. Sauvegarde et restauration décrites en code.

**Non tenu à ce jour.** Le chiffrement du transport, le moindre privilège au niveau de la base, la
révocation de session et la limitation de débit. Trois de ces quatre points sont déjà écrits et
désactivés par un interrupteur : ce n'est pas de l'intention, c'est du travail fait qu'on n'a pas
activé, et la différence se vérifie dans le dépôt.

---

## Annexe A, preuves reproductibles

Chaque contrôle annoncé se vérifie par une commande.

**Aucune requête SQL construite par concaténation** :

```bash
grep -rn 'text(f\|execute(f\|\.format(' services/backend/app --include=*.py
```

**Le playbook passe l'analyse statique au profil le plus strict** :

```bash
cd infra/ansible && ansible-lint site.yml
```

**Règles de pare-feu réellement appliquées**, sur la VM :

```bash
ufw status verbose
```

**Aucun service interne joignable hors de la machine** :

```bash
docker compose ps --format '{{.Name}}\t{{.Ports}}'
```

**Droits et propriétaire du fichier de secrets**, sur la VM :

```bash
ls -l /opt/enervision/.env      # -rw------- enervision enervision
```

**Aucun fichier d'environnement suivi par git**, hors exemple :

```bash
git ls-files | grep -E '\.env'
```

**Révision réellement en service** :

```bash
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
  ghcr.io/alexisdraud/smart-energy-optimizer-backend:main
```

**Rapports de vulnérabilités** : artefacts `trivy-image-reports-<sha>` de chaque exécution de la
chaîne, conservés trente jours, au format JSON, avec le compte par sévérité dans le résumé du job.

**Variables obligatoires du compose** :

```bash
grep -o '\${[A-Z_]*:?' docker-compose.yml | sort -u
```

## Annexe B, remédiation des vulnérabilités, 08/09/2026

Trace datée du travail de remédiation, conservée parce qu'elle documente des décisions et pas
seulement un résultat.

**Backend.** Passage à `mlflow-skinny` aligné sur la version du service d'entraînement, avec le
chargement des modèles et les clients d'artefacts, sans le paquet complet ni sa dépendance
`pyarrow`. Cette version dépasse les versions corrigées des CVE MLflow qui en ont une. Le paquet
allégé contient encore du code partagé : ce n'est donc pas une preuve que toute CVE sans correctif a
disparu. En particulier, une CVE visant les points d'entrée de jobs du serveur ne concerne pas le
backend, qui n'en expose aucun. À réévaluer avant d'activer l'exécution de jobs côté serveur
d'entraînement, et à ne charger que des artefacts de confiance, `cloudpickle` pouvant exécuter du
code à la désérialisation.

**Base des images.** Le backend utilise Ubuntu 24.04 LTS, dont les dépôts fournissent les correctifs
des trois alertes `CRITICAL` sur `perl-base` que Debian n'avait pas. Le build vérifie que la version
corrigée est bien présente. Le runtime web exige une version corrigée de `libuuid`, qui couvre sept
alertes `HIGH` du premier rapport.

Aucune exception Trivy n'a été écrite et aucun seuil n'a été abaissé : les vulnérabilités ont été
corrigées, pas masquées. Les images doivent être reconstruites régulièrement, une CVE publiée après
un build n'étant visible qu'au scan suivant.

**Limite du contrôle.** Trivy détecte ce que sa base contient au moment de l'exécution. Il ne
remplace ni un test dynamique de l'API, ni une analyse des erreurs de logique métier, ni un test
d'intrusion, ni la surveillance de l'environnement en exécution.
