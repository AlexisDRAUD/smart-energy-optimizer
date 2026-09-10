# Infrastructure

L'infrastructure comme code du projet est dans [`ansible/`](ansible/).

Le Proxmox n'étant pas administré par l'équipe, il n'y a pas d'étage de provisionnement : le
périmètre est la configuration de la VM et le déploiement de la pile. La décision et ses
conséquences sont expliquées dans [`deploiement.md`](../docs/deploiement.md).
