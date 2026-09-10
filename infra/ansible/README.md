# Playbook Ansible

L'infrastructure comme code du projet. Le contexte, les décisions et les limites sont dans
[`../../docs/deploiement.md`](../../docs/deploiement.md), qui fait foi. Ce fichier est le
mémo opérationnel.

Uniquement des modules `ansible.builtin`. Le playbook tourne sans `ansible-galaxy`, donc sans
dépendre d'un accès réseau depuis le poste qui l'applique.

## Lancer

```bash
cd infra/ansible
cp inventory.example.ini inventory.ini     # renseigner l adresse et l utilisateur
ansible-playbook site.yml --check --diff   # simulation, aucune ecriture
ansible-playbook site.yml                  # application
ansible-playbook site.yml --tags deploy    # redeploiement seul
```

Prérequis sur le poste : `pip install ansible-core`. Sur la VM : un accès SSH et un compte
disposant de `sudo`. `inventory.ini` n'est pas versionné.

En fonctionnement normal, ce playbook n'est pas lancé à la main : le job `deploy` de la chaîne
d'intégration le rejoue depuis la VM à chaque fusion dans `main`.

## Les étiquettes

| Étiquette | Contenu |
|---|---|
| `base` | paquets de base, dont `acl` et `ansible-core` |
| `users` | groupe et compte de service, règle `sudo` du compte de déploiement, durcissement SSH optionnel |
| `docker` | moteur ou greffon compose selon la machine, rotation des journaux, service activé au démarrage |
| `firewall` | ufw, ouverture de SSH et du port du dashboard, tout le reste fermé |
| `app` | répertoire applicatif, dépôt à jour, fichier d'environnement en droits 600 |
| `deploy` | tirage forcé des images puis démarrage de la pile |
| `backup` | scripts de sauvegarde et de restauration, tâche planifiée quotidienne |
| `dbrole` | rôle base au moindre privilège, désactivé par défaut |
| `runner` | runner GitHub auto-hébergé, seulement si un jeton est fourni |

## Les interrupteurs

Quatre variables sont à `false` par défaut. Leur raison d'être est expliquée dans
`docs/deploiement.md`, elles ne s'activent pas par curiosité.

```bash
ansible-playbook site.yml --tags users    -e harden_ssh=true
ansible-playbook site.yml --tags firewall -e enable_https=true
ansible-playbook site.yml --tags dbrole   -e create_app_role=true -e app_role_password=...
ansible-playbook site.yml --tags runner   -e runner_token=XXXX
```

`install_docker` reste à `false` parce que la VM de l'école fournit déjà le moteur et que son
réseau refuse le dépôt officiel Docker. Sur une machine vierge qui joint ce dépôt, le repasser à
`true`.

Le jeton d'enregistrement du runner est court et se récupère dans les réglages du dépôt, onglet
Actions, Runners. Il se passe en ligne de commande, jamais dans un fichier.

## Vérifications

```bash
ansible-playbook site.yml --syntax-check
ansible-lint site.yml
```

`ansible-lint` passe au profil `production`, son niveau le plus strict.
