# Changelog

Versions selon SemVer. Une entrée **« change les résultats »** signale toute modification qui
déplace un montant calculé pour une année déjà publiée; elle cite la source officielle qui la
justifie.

## 0.2.0 — 2026-10-04

- **Pension alimentaire pour enfants** (`compute_child_support`) : Formulaire de fixation des
  pensions alimentaires pour enfants, parties 2 à 6, ligne par ligne; tables de fixation et
  déduction de base 2025 et 2026 tirées des publications du ministère de la Justice et vérifiées à
  la lecture; choix automatique de la section du temps de garde; capacité de payer; avertissements
  au-delà de 200 000 $ (montant indicatif) et au-delà de 6 enfants. Validation : les trois exemples
  chiffrés du guide officiel (sections 1, 1.1 et 3) et l'équivalence de la section 4 avec les autres.
- `ParentIncome.from_tax_return` : revenus du formulaire de fixation tirés d'une déclaration TP-1.

## 0.1.0 — 2026-10-04

- **Impôt minimum de remplacement** : T691 au fédéral (ligne 41700, abattement du Québec calculé
  sur le montant minimum), annexe E et TP-776.42 au Québec (ligne 432). Avertissement quand il
  s'applique; report sur sept ans non modélisé.
- **Crédit pour prolongation de carrière** (ligne 391) : 14 % du revenu de travail au-delà de
  l'exclusion, plafonné, réduit de 7 % du revenu net au-delà du seuil, limité à l'impôt restant.
- Relevés de l'oracle : 6 cas de plus par année (38); concordance exacte de l'IMR fédéral et du
  crédit pour prolongation de carrière.
- **Oracle externe hors dépôt** : ses relevés et notes d'écarts passent dans `oracle/AAAA/`
  (ignoré par git); il n'est plus nommé nulle part. Chaque relevé déclare ses écarts connus
  (`ecarts_connus`), et les tests qui le lisent sont sautés en son absence. Les deux points
  d'interprétation sont documentés dans `PLAN.md`.
- **Année 2025** : `parametres/2025/*.toml`, lus sur les formulaires 2025 (5005-R, 5000-D1, TP-1
  et annexes B, F, K, R, U), sans changer une ligne de code. 32 cas fictifs 2025 contre l'oracle externe : concordance
  complète, sauf l'écart REER à l'annexe B. Les tests de paramètres et de validation couvrent
  désormais chaque année livrée.
- Relevés de l'oracle refaits sans l'allocation canadienne pour les travailleurs (hors portée) :
  l'écart d'E30 disparaît.
- Paramètres 2026 (`parametres/2026/*.toml`) avec source officielle par table; chargeur
  `load_parameters(year)` qui vérifie le schéma; `provisional()` liste les valeurs provisoires.
- `rules` : barèmes, montant personnel de base et âge fédéraux, RRQ/AE/RQAP, Annexe B, FSS,
  dividendes, remboursement de la PSV. Concordance avec l'oracle externe sur les 32 cas.
- `compute(Taxpayer) -> TaxReturn` : T1 (5005-R) et TP-1 avec annexes B, F et K, ligne par ligne,
  numéros et libellés officiels (formulaires 2025), `to_dict()` pour un agent, avertissements
  quand une règle provisoire ou non calculée touche le contribuable.
- Validation contre l'oracle externe sur les 32 cas : toutes les lignes concordent, sauf trois écarts
  déclarés et vérifiés à leur valeur exacte (points d'interprétation du `PLAN.md`).

## 0.0.1 — 2026-10-04

- Socle du dépôt : licence AGPL-3.0-or-later, consignes, plan, squelette du paquet.
- 32 contribuables fictifs (14 salariés, 18 retraités) relevés sur un calculateur externe, environ
  47 lignes chacun.
