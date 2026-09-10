# Déploiement

Livrable EC04, avec `rapport-securite.md`. Décrit la machine cible, l'infrastructure comme code et
le chemin qui mène d'une fusion dans `main` à l'application en service.

## La machine

Une VM du Proxmox de l'école, `10.138.200.30`, 4 cœurs, 8 Go de mémoire, 64 Go de disque. Le Proxmox
n'est pas administré par l'équipe, seule la VM l'est. L'accès est fourni en `root` par mot de passe,
sans console de secours.

Deux conséquences qui gouvernent tout le reste. Le runner GitHub refuse de s'installer sous `root`,
il faut donc un compte dédié. Et le durcissement SSH du playbook, qui coupe la connexion `root`,
fermerait la seule porte de la machine : il est désactivé par défaut et documenté comme tel.

Trois comptes cohabitent :

| Compte | Rôle |
|---|---|
| `root` | administration de la machine, seul accès fourni par l'école |
| `deploy` | porte le runner GitHub, dispose de `sudo` sans mot de passe pour rejouer le playbook |
| `enervision` | compte de service, propriétaire de `/opt/enervision`, membre du groupe `docker`, ne se connecte pas |

## L'infrastructure comme code

Tout est dans `infra/ansible/`. Un seul play, uniquement des modules `ansible.builtin`, donc aucune
dépendance à `ansible-galaxy` ni au réseau du poste qui l'applique.

Le périmètre est la **configuration** de la machine et le déploiement de la pile. Il n'y a pas
d'étage de provisionnement : le Proxmox n'étant pas administré par l'équipe, Terraform n'aurait
aucune ressource à décrire. Si la plateforme était à nous, la création de la VM se décrirait avec le
provider `bpg/proxmox` et ce playbook resterait l'étage de configuration, inchangé.

Neuf étiquettes permettent de rejouer un étage sans toucher aux autres :

| Étiquette | Contenu |
|---|---|
| `base` | paquets de base, dont `acl` et `ansible-core` |
| `users` | groupe et compte de service, règle `sudo` du compte de déploiement, durcissement SSH optionnel |
| `docker` | moteur et greffon compose, rotation des journaux, service activé au démarrage |
| `firewall` | ufw, ouverture de SSH et du port du dashboard, tout le reste fermé |
| `app` | répertoire applicatif, dépôt à jour, fichier d'environnement en droits 600 |
| `deploy` | tirage des images puis démarrage de la pile, et affichage de l'état |
| `backup` | scripts de sauvegarde et de restauration, tâche planifiée quotidienne |
| `dbrole` | rôle base au moindre privilège, désactivé par défaut |
| `runner` | runner GitHub auto-hébergé, seulement si un jeton est fourni |

```bash
cd infra/ansible
ansible-playbook site.yml --check --diff   # simulation
ansible-playbook site.yml                  # application
ansible-playbook site.yml --tags deploy    # redéploiement seul
```

Le playbook passe `ansible-lint` au profil `production`, son niveau le plus strict.

### Ce que la VM impose, et qui est déclaré dans le code

Trois contraintes découvertes au premier déploiement réel. Elles sont dans le playbook plutôt que
dans une manipulation manuelle non tracée, ce qui est précisément l'intérêt de l'IaC.

- **`install_docker` vaut `false`.** La VM arrive avec le moteur Docker, et son réseau refuse
  `download.docker.com`. Les tâches d'installation depuis le dépôt officiel sont donc
  conditionnelles. Sur une machine vierge qui joint ce dépôt, repasser la variable à `true`.
- **Le greffon compose vient de la distribution.** La machine ne fournissait que `docker-compose`
  en version 1, qui ne sait pas lire ce fichier compose : ni la spécification sans clé `version`,
  ni les conditions de démarrage entre services, ni `pull_policy`. Le playbook installe
  `docker-compose-v2` par apt quand `install_docker` vaut `false`.
- **`acl` fait partie des paquets de base.** Sans lui, Ansible ne sait pas donner ses fichiers
  temporaires à un compte non privilégié et chaque tâche en `become_user` échoue sur un `chmod`
  invalide.

### Interrupteurs désactivés par défaut

| Variable | Défaut | Pourquoi |
|---|---|---|
| `harden_ssh` | `false` | pose `PermitRootLogin no`, ce qui fermerait le seul accès de la machine |
| `enable_https` | `false` | le port 443 reste fermé tant qu'aucun frontal TLS n'écoute derrière |
| `create_app_role` | `false` | basculer l'application sur le rôle restreint demande deux URL de connexion distinctes |
| `install_docker` | `false` | voir ci-dessus |

Le port 443 mérite un mot. Ouvrir un port en prévision d'un service qui n'existe pas est un confort,
pas un principe, et c'est exactement ce que le moindre privilège interdit. Une seconde tâche
**retire** la règle quand `enable_https` vaut `false`, pour que le playbook sache refermer autant
qu'ouvrir. C'est ce qui fait qu'il décrit un état et pas une suite de gestes.

## L'amorçage

La machine doit pouvoir faire tourner un playbook avant que le playbook ait pu la préparer. Quatre
commandes, une seule fois dans la vie de la machine, en SSH sur la VM :

```bash
apt update && apt install -y ansible-core
echo "deploy ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/deploy
chmod 0440 /etc/sudoers.d/deploy
visudo -c
```

Puis le runner GitHub, installé sous le compte `deploy` avec les commandes que donne la page
**Settings, Actions, Runners, New self-hosted runner**, et passé en service avec
`./svc.sh install deploy` puis `./svc.sh start`.

Une machine ne peut pas s'accorder elle-même les droits dont elle a besoin pour se les accorder.
Tous les systèmes de ce type ont ce point de départ manuel.

## Le déploiement courant

À partir de là, une fusion dans `main` suffit. Le job `deploy` de la chaîne d'intégration rejoue ce
playbook depuis la VM, avec le fichier d'environnement issu du secret de dépôt `PROD_ENV`. Le détail
des étapes est dans `ci.md`.

### Les images et le retour arrière

`prod.env` fixe `IMAGE_REGISTRY`, `IMAGE_TAG` à `main` et `IMAGE_PULL_POLICY` à `missing`.

`missing` est nécessaire au redémarrage de la machine : les conteneurs repartent alors sur l'image
locale, sans avoir à joindre le registre alors qu'aucun identifiant ne vit sur la VM.

Ce réglage a une conséquence que la tâche de tirage doit compenser explicitement. `docker compose
pull` **respecte le `pull_policy` de chaque service**, donc avec `missing` il saute toute image déjà
présente et n'actualise jamais une étiquette mobile. La tâche utilise donc
`docker compose pull --policy always`, qui force le tirage pour cette commande seulement, pendant
que le job est authentifié. Deux moments distincts, deux comportements distincts.

Pour revenir à une version précise, mettre l'empreinte du commit voulu dans `IMAGE_TAG` et
redéployer. La procédure est décrite et possible, elle n'a pas été éprouvée.

## Exploitation

La sauvegarde, la restauration, la rotation des journaux et le démarrage automatique font partie du
playbook et ne sont pas des gestes manuels.

- **Sauvegarde** : tâche planifiée quotidienne, `pg_dump` compressé, écrit d'abord sous un nom
  temporaire et renommé seulement en cas de succès, donc un fichier au nom définitif est toujours un
  fichier complet. Rotation par ancienneté, échec explicite si l'archive est vide.
- **Restauration** : `/usr/local/bin/enervision-restore-db <archive>`, avec confirmation, arrêt des
  services applicatifs le temps de l'opération, puis redémarrage. Rien ne restaure automatiquement
  au démarrage, ce qui écraserait une base saine au moindre redémarrage.
- **Journaux Docker** : plafonnés en taille et en nombre de fichiers dans la configuration du démon.
  Un disque plein est la panne la plus banale d'une machine qu'on administre soi-même.
- **Démarrage automatique** : service Docker activé au boot, et `restart: unless-stopped` sur tous
  les conteneurs de service, base et MLflow compris.

Le détail des gestes courants est dans `runbook.md`.

## Ce qui n'est pas fait

- **Pas de HTTPS.** Il faudrait un frontal TLS devant le conteneur `web`, et `COOKIE_SECURE` à
  `true` une fois en place. Le port 443 reste fermé jusque-là.
- **Pas de provisionnement de la VM**, hors périmètre.
- **La restauration n'a jamais été jouée.** Une sauvegarde dont la restauration n'a pas été essayée
  n'est pas une sauvegarde. Le script existe pour que l'essai tienne en une commande.
- **Les sauvegardes vivent sur le disque qu'elles protègent.** Elles couvrent l'erreur humaine et la
  corruption, pas la perte de la machine.
- **Destruction et remontée complète non éprouvées.** Ansible n'a pas d'état et ne tient pas la
  liste de ce qu'il a créé, il ne sait donc pas défaire. Ce que garantit ce playbook, ce n'est pas
  de détruire, c'est de **remonter depuis une machine vierge**.
