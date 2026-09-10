# Documentation EnerVision

Point d'entrée de la documentation. Chaque document couvre un sujet, et le tableau ci-dessous dit
lequel répond à quel livrable.

## Correspondance avec les livrables

### EC03, intégration et déploiement continus

Livrables attendus : une chaîne CI/CD fonctionnelle et la documentation des processus d'intégration
continue.

| Livrable | Où |
|---|---|
| La chaîne elle-même | `.github/workflows/ci.yml` |
| Documentation du processus | [`ci.md`](ci.md) |
| Tests, qualité et couverture | [`tests-et-qualite.md`](tests-et-qualite.md) |

### EC04, déploiement et sécurisation

Livrables attendus : l'application déployée et le rapport de sécurisation.

| Livrable | Où |
|---|---|
| L'application déployée | `http://10.138.200.30` |
| Infrastructure comme code | `infra/ansible/`, décrit dans [`deploiement.md`](deploiement.md) |
| Rapport de sécurisation | [`rapport-securite.md`](rapport-securite.md) |
| Preuves de scan | artefacts `trivy-image-reports-<sha>` de la chaîne, trente jours |
| Exploitation courante | [`runbook.md`](runbook.md) |

### EC05, analyse automatisée et interface

Livrables attendus : l'application d'analyse automatisée, l'interface utilisateur et la
documentation technique.

| Livrable | Où |
|---|---|
| Chaîne d'analyse | services `collector`, `etl`, `model` du `docker-compose.yml` |
| Interface utilisateur | [`interface.md`](interface.md) |
| Documentation technique | [`architecture.md`](architecture.md) et le schéma, [`architecture.png`](architecture.png) ou sa source [`architecture.mmd`](architecture.mmd) |
| Contrat de données | [`data-contract.md`](data-contract.md) |
| Contrat d'API | [`api-contract.md`](api-contract.md) |

### EC06, automatisation et pilotage

Livrables attendus : les outils ou scripts d'automatisation et la documentation de pilotage.

| Livrable | Où |
|---|---|
| Entraînement, service et surveillance du modèle | [`ml.md`](ml.md) |
| Scripts d'exploitation | `infra/ansible/templates/`, décrits dans [`deploiement.md`](deploiement.md) |
| Scripts de démarrage et de reprise | `services/backend/scripts/`, décrits dans [`runbook.md`](runbook.md) |
| Entraînements planifiés | `.github/workflows/train.yml` et `mlflow_pipeline.yml` |

## Tous les documents

| Document | Contenu |
|---|---|
| [`setup.md`](setup.md) | démarrer le projet sur un poste |
| [`configuration.md`](configuration.md) | toutes les variables d'environnement |
| [`architecture.md`](architecture.md) | vue d'ensemble, étages de données, choix et limites |
| [`data-contract.md`](data-contract.md) | tables, colonnes, contraintes, règles de validation |
| [`api-contract.md`](api-contract.md) | routes, paramètres, réponses, codes d'erreur |
| [`interface.md`](interface.md) | écrans, indicateurs métier, états de chargement |
| [`ci.md`](ci.md) | chaîne d'intégration et de déploiement |
| [`tests-et-qualite.md`](tests-et-qualite.md) | suites de tests, outils de qualité, couverture |
| [`deploiement.md`](deploiement.md) | machine cible, playbook Ansible, images, exploitation |
| [`rapport-securite.md`](rapport-securite.md) | périmètre, menaces, contrôles, risques acceptés |
| [`runbook.md`](runbook.md) | gestes courants et pannes connues |
| [`ml.md`](ml.md) | modèle, entraînement, mise en service, pilotage |

## Conventions

Chaque document dit ce qui est fait **et ce qui ne l'est pas**, dans une section finale. Une
documentation qui annonce ses trous est plus utile qu'une documentation qui les cache, et elle reste
vraie plus longtemps.

Les documents ne se répètent pas. Quand un sujet est traité ailleurs, le document renvoie vers celui
qui fait foi plutôt que d'en recopier une version qui divergera.
