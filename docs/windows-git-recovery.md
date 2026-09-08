# Diagnostic Git sous Windows

Cette procédure traite les erreurs `Permission denied` ou `Access is denied` sur
les packfiles et les anciens worktrees sans supprimer manuellement de contenu dans
`.git`, sans reset et sans perdre de commit.

## Contrôles sans écriture

Depuis la racine du dépôt, dans PowerShell :

```powershell
git status --short --branch
git worktree list --porcelain
git worktree prune --dry-run --verbose
git rev-parse -q --verify MERGE_HEAD
Get-ChildItem -LiteralPath .git -Recurse -Force -Filter *.lock -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -in @('git.exe', 'git-lfs.exe', 'ssh.exe') } |
    Select-Object ProcessId, ParentProcessId, CreationDate, CommandLine
git fsck --full --no-reflogs
git multi-pack-index verify
```

Un `MERGE_HEAD` ou un fichier `.lock` demande d'identifier l'opération Git qui
l'utilise avant toute autre action. Ne jamais effacer un verrou tant que le processus
propriétaire est actif.

## Processus Git suspendu

Fermer d'abord le terminal ou la tâche IDE qui a lancé la commande. Si le processus
reste présent, relever son PID et sa ligne de commande, vérifier à nouveau l'absence
de `MERGE_HEAD`, puis arrêter uniquement ce PID :

```powershell
Stop-Process -Id <PID>
git status --short --branch
git fsck --full --no-reflogs
```

Ne pas arrêter globalement tous les processus Git ou SSH : un tunnel SSH ou une autre
copie de travail peut être légitime.

## Packfiles et permissions

Contrôler les attributs, le propriétaire et les droits sans les modifier :

```powershell
Get-ChildItem -LiteralPath .git\objects\pack -Force |
    Select-Object Name, Length, Attributes, LastWriteTime
Get-Acl -LiteralPath .git\objects\pack | Format-List Owner, AccessToString
```

L'attribut `ReadOnly` d'un objet Git ne prouve pas à lui seul une ACL défectueuse.
Une erreur intermittente provient souvent d'un handle ouvert par Git, l'IDE, un outil
de sauvegarde ou l'antivirus. Fermer ces opérations, puis répéter les contrôles avant
de changer des droits ou des attributs.

Si l'accès reste impossible alors que l'intégrité du dépôt est bonne, créer un nouveau
clone dans un autre dossier, récupérer toutes les branches et vérifier que le commit de
travail y existe. Conserver l'ancien dossier intact jusqu'à validation complète du clone.

## Worktrees

Toujours créer et retirer une copie de travail avec Git :

```powershell
git worktree add <dossier> <branche>
git worktree remove <dossier>
git worktree list --porcelain
```

Ne pas supprimer directement le dossier d'un worktree dans l'Explorateur. Si un ancien
dossier a déjà disparu, commencer par `git worktree list` et le mode `--dry-run`; ne pas
nettoyer `.git/worktrees` à la main.

## Prévention

- Utiliser le même compte Windows et le même niveau d'élévation pour le terminal et l'IDE.
- Attendre la fin d'un fetch, merge, rebase, maintenance ou indexation avant d'en lancer un autre.
- Fermer proprement les terminaux qui attendent un éditeur ou une saisie Git.
- Exclure seulement le dossier de travail de l'analyse antivirus si la politique du poste
  l'autorise ; ne jamais désactiver globalement la protection.
- Vérifier `git status` avant et après chaque opération portant sur un worktree.

## État constaté le 8 septembre 2026

- dépôt sur `EADL_2025_NIORT_G1/FIX-Dashboard`, propre au début du diagnostic ;
- `git fsck` et la vérification du multi-pack-index réussis ;
- aucun verrou Git et aucune fusion enregistrée ;
- ancien dossier `smart-energy-optimizer-pr30-review` absent et non enregistré ;
- processus `git merge dev` suspendu depuis plusieurs heures, sans `MERGE_HEAD`, arrêté
  après ces vérifications ;
- propriétaire des packfiles : `AD\cvanzetta2023`, avec contrôle total ; certains fichiers
  portaient l'attribut `ReadOnly`, sans preuve d'un refus ACL persistant.
