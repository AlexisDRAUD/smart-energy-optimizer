# Déploiement de la VM avec Ansible

L'infrastructure comme code du projet. Le Proxmox n'est pas administré par l'équipe, seule
la VM l'est, donc il n'y a rien à provisionner : le périmètre est la configuration de la
machine et le déploiement de la pile.

Uniquement des modules `ansible.builtin`. Le playbook tourne sans `ansible-galaxy`, donc sans
dépendre d'un accès réseau depuis le poste qui l'applique.

## Prérequis

Sur le poste, pas sur la VM :

```bash
pip install ansible-core
```

Sur la VM, un accès SSH par clé et un compte disposant de `sudo`.

## Mise en route

```bash
cd infra/ansible
cp inventory.example.ini inventory.ini     # renseigner l'adresse et l'utilisateur
ansible-playbook site.yml --check --diff   # simulation, aucune écriture
ansible-playbook site.yml                  # application
```

Le fichier d'environnement déposé sur la VM est celui désigné par `env_file_src`, par défaut
`prod.env` à la racine du dépôt. Il n'est pas versionné et contient les secrets. `inventory.ini`
n'est pas versionné non plus.

## Ce que fait le playbook

| Étiquette | Contenu |
|---|---|
| `base` | paquets de base |
| `users` | groupe et compte de service dédiés, non root, membre du groupe docker |
| `docker` | moteur Docker, greffon compose, rotation des journaux, service activé au démarrage |
| `firewall` | ufw, ouverture de SSH, du port du dashboard et de 443, tout le reste fermé |
| `app` | répertoire applicatif, dépôt à jour, fichier d'environnement en droits 600 |
| `deploy` | `docker compose pull` puis `up -d`, et affichage de l'état |
| `backup` | scripts de sauvegarde et de restauration, tâche planifiée quotidienne |
| `dbrole` | rôle base au moindre privilège, désactivé par défaut |
| `runner` | runner GitHub auto-hébergé, seulement si un jeton est fourni |

Rejouer un seul étage :

```bash
ansible-playbook site.yml --tags deploy
```

## Ce qui est volontairement désactivé par défaut

**`harden_ssh`.** Couper l'authentification par mot de passe avant d'avoir vérifié que sa clé
fonctionne, c'est se fermer la porte de la VM. À activer une fois la connexion par clé établie :

```bash
ansible-playbook site.yml --tags users -e harden_ssh=true
```

**`create_app_role`.** Le rôle applicatif au moindre privilège se crée sans risque, mais y
faire basculer l'application demande de donner deux URL de connexion au compose, une pour les
migrations avec le compte propriétaire et une pour l'API avec le rôle restreint. C'est une
modification à faire sciemment, pas la veille d'une livraison.

```bash
ansible-playbook site.yml --tags dbrole -e create_app_role=true -e app_role_password=...
```

**`runner_token`.** Le jeton d'enregistrement du runner est court et se récupère dans les
réglages du dépôt, onglet Actions, Runners. Il se passe en ligne de commande, jamais dans un
fichier :

```bash
ansible-playbook site.yml --tags runner -e runner_token=XXXX
```

## L'amorçage

La première application se fait à la main depuis un poste, puisque le runner n'existe pas
encore. Une fois le runner installé, le job de déploiement de la chaîne d'intégration prend le
relais et rejoue ce même playbook sur la machine. Tous les systèmes de ce type ont ce point de
départ manuel, et savoir l'expliquer vaut mieux que de le masquer.

## Vérifications faites sur ce playbook

```bash
ansible-playbook site.yml --syntax-check
ansible-lint site.yml
```

`ansible-lint` passe au profil `production`, son niveau le plus strict.

## Ce qui n'est pas couvert

- **Pas de HTTPS.** Il faudrait un frontal TLS devant le conteneur `web`, et `COOKIE_SECURE`
  à `true` une fois en place. Le port 443 est déjà ouvert par le pare-feu pour ce jour-là.
- **Pas de provisionnement de la VM elle-même**, qui est fournie par l'école. Si le Proxmox
  était administré par l'équipe, la création de la machine se décrirait en Terraform avec le
  provider correspondant, et ce playbook resterait l'étage de configuration.
- **La restauration n'a pas encore été essayée.** Une sauvegarde dont la restauration n'a
  jamais été jouée n'est pas une sauvegarde. Le script existe pour que l'essai tienne en une
  commande.
