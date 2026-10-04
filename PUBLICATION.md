# Publication sur GitHub

Destination décidée le 2026-10-04 : dépôt GitHub `plcharbonneau/impotsQC`, code sous
AGPL-3.0-or-later. Le dépôt est d'abord **privé**; le rendre public reste une décision du mainteneur.

## Fait avant le premier envoi (2026-10-04)

- [x] **Historique propre** : le dépôt publié commence par un commit initial unique (0.2.0).
      L'historique de développement, qui contenait les relevés d'un oracle externe et des messages
      qui le nommaient, reste sur la branche locale `historique-local`, jamais envoyée.
- [x] **Courriel des commits** : adresse `noreply` de GitHub (configurée dans ce dépôt).
- [x] **Relecture de confidentialité** : aucune donnée personnelle, aucun relevé d'oracle (dossier
      `oracle/` ignoré par git), aucune mention de dépôt privé.

## À faire avant de rendre le dépôt public

- [ ] Intégration continue : `pytest` sur Python 3.11 à 3.14 (sans `oracle/`, les tests de
      validation externe sont sautés; ceux du moteur, des paramètres et des conventions s'exécutent).
- [ ] Relire le README comme un visiteur : portée, limites, aucun conseil fiscal.
- [ ] Ne jamais pousser la branche `historique-local`.
