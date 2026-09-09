# Infrastructure

Aucun secret dans ce dossier.

- `ansible/` : configuration de la VM et déploiement de la pile. C'est l'infrastructure comme
  code du projet. Voir `ansible/README.md`.
- `terraform/` : vide. Le Proxmox n'étant pas administré par l'équipe, il n'y a pas de machine
  à provisionner. Si cela changeait, la création de la VM se décrirait ici, et le playbook
  Ansible resterait l'étage de configuration.
