# CLAUDE.md — impotsqc

Consignes pour les agents (Claude Code, Codex) qui travaillent dans ce dépôt. Réponses à
l'utilisateur en français. **API en anglais, documentation et messages en français.**

## Ce qu'est ce dépôt

Une librairie Python qui calcule les déclarations T1 (fédérale) et TP-1 (Québec) **ligne par
ligne**, avec annexes, pour un script ou un agent. Elle sert aussi de module fiscal à `retraiteqc`
(`../retraiteqc`), qui l'appellera directement.

**Décisions du 2026-10-04 (PL) :**
- portée fédéral + Québec;
- salarié ET retraité dès la première version;
- appel direct depuis `retraiteqc`;
- licence **AGPL-3.0-or-later**;
- destination finale : **dépôt GitHub public**.

Aucun remote ni envoi sans le feu vert explicite de PL : publier est irréversible.

## Règles

- **Aucune donnée personnelle.** Ni revenus réels, ni âge, ni solde de PL ou de qui que ce soit.
  Les tests et la validation utilisent des contribuables fictifs aux montants ronds.
- **Paramètres : sources officielles seulement** (ARC, Revenu Québec, Retraite Québec, RAMQ,
  ministères des Finances). Chaque valeur d'un TOML porte sa source : URL + titre du document
  et, si possible, la page ou la ligne. Une valeur sans source n'entre pas.
- **Oracles externes : jamais nommés, jamais committés.** Un calculateur tiers peut servir d'oracle
  de validation, mais il n'est nommé nulle part dans le dépôt : ni code, ni tests, ni documentation,
  ni messages de commit (demande de PL, 2026-10-04). Ses relevés et les notes d'écarts qui le
  nomment vivent dans `oracle/AAAA/` (ignoré par git); chaque relevé déclare ses écarts connus
  (`ecarts_connus`), et les tests qui le lisent sont sautés en son absence. On ne copie ni son code,
  ni ses textes, ni ses paramètres. Un écart s'explique par un document officiel, dans un sens ou
  dans l'autre; il ne se corrige jamais en recopiant l'oracle.
- **Un dossier par année** pour les paramètres (`src/impotsqc/parametres/AAAA/`) et les relevés de
  l'oracle (`oracle/AAAA/`, local). **Les formules sont communes.** Quand la forme d'une règle change
  (nouveau crédit, nouvelle méthode), on ajoute une variante choisie par une clé du TOML de
  l'année. Ne jamais dupliquer un module entier par année.
- **Une année publiée ne se modifie pas.** Corriger une erreur avérée d'une année publiée =
  version mineure + entrée « change les résultats » au `CHANGELOG.md`, avec la source officielle
  qui la justifie.
- **Python seulement, code simple** (même règle que `retraiteqc`), sans dépendance d'exécution :
  `tomllib` suffit. Une accélération (Rust, table précompilée) ne s'envisage qu'après une mesure
  qui montre que l'impôt est le goulot de `retraiteqc`. Elle serait alors validée contre la
  version Python, qui reste l'oracle.
- Chaque fichier Python commence par l'en-tête SPDX `AGPL-3.0-or-later`. Chaque fonction et
  classe publique porte une docstring en français.
- Les messages de commit ne nomment aucun modèle ni outil (pas de ligne `Co-Authored-By:` pour
  Claude ou Codex) : les deux agents travaillent dans ce dépôt.
- Les lignes sont désignées par leur **numéro officiel** (T1 : `"23600"`; TP-1 : `"275"`), avec
  le libellé officiel. Les montants intermédiaires d'une annexe sont nommés `"<annexe>:<ligne>"`.

## Commandes

```bash
uv venv .venv && uv pip install -e ".[test]" --python .venv/bin/python
.venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python script.py   # sous ~/Documents, Python 3.14 ignore les .pth (drapeau « caché »)
```

## Documentation des librairies : Context7 d'abord

Pour toute question sur une librairie, un framework, un outil ou une API — même connus (pytest,
uv et `uv_build`, `tomllib`, packaging Python) —, interroger le MCP Context7 avant de répondre ou
de coder : syntaxe, configuration, migration de version, débogage propre à la librairie,
installation. Le faire même quand la réponse semble connue; préférer Context7 à la recherche web
pour la documentation. Étapes : `resolve-library-id` (sauf identifiant `/org/projet` déjà
fourni), retenir la meilleure correspondance, puis `query-docs` avec une question précise, un
appel par concept. Pas pour : la fiscalité elle-même (sources officielles), le code écrit de zéro,
la revue de code, les concepts généraux. Codex reçoit Context7 de sa configuration globale
(`~/.codex/config.toml`) : ne pas le redéfinir dans un `.codex/config.toml` de ce dépôt.
