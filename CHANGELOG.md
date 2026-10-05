# Changelog

Versions selon SemVer. Une entrée **« change les résultats »** signale toute modification qui
déplace un montant calculé pour une année déjà publiée; elle cite la source officielle qui la
justifie.

## 0.6.0 — en préparation

**Change l'API et change les résultats.** Les valeurs numériques des paramètres existants
restent inchangées; les formules erronées et les revenus désormais explicitement saisis sont
traités conformément aux sources officielles.

- Entrées `PensionIncome`, `Benefits` et `Deductions` : rentes RPA/REER, FERR admissibles de
  survivant, AE/RQAP, suppléments fédéraux, aide sociale, indemnités, trop-perçus remboursés,
  cotisations RPA et cotisations syndicales/professionnelles distinctes fédéral/Québec.
  Les inconnues déterminantes bloquent le calcul et fournissent les questions à poser.
- Nouveau document `5000-D1`, grilles `23500-*`, `25000-*` et `31400-*`. Récupération AE
  avant PSV/SRG, déduction des suppléments réduite de la part récupérée. Sources :
  [feuille de travail fédérale 2025](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5000-d1/5000-d1-25f.pdf),
  [T4E 2025](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t4e/t4e-25b.pdf),
  [T4E 2026](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t4e/t4e-26b.pdf),
  [déduction 25000](https://www.canada.ca/fr/agence-revenu/services/impot/particuliers/sujets/tout-votre-declaration-revenus/declaration-revenus/remplir-declaration-revenus/deductions-credits-depenses/ligne-25000-deduction-autres-paiements.html).
- **Correction REER ordinaire** : composante de `TP-1:122` → `TP-1:154`; elle n'alimente plus
  le crédit de retraite de l'annexe B. Les rentes de REER échu et paiements de FERR restent à
  122. Le revenu total ne change pas; l'impôt peut augmenter si l'ancien crédit était accordé.
  Source : [TP-1, ligne 154, point 6](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/96-a-164-revenu-total/ligne-154/point-6/).
- Le revenu net fédéral est borné à zéro. L'IMR conserve cependant la base signée avant les
  rajouts, dans les deux régimes. Ajout de la déduction pour travailleur au TP-776.42 et des
  cotisations syndicales au T691. Sources :
  [T691, partie 1 et note 1](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t691/t691-25f.pdf),
  [TP-776.42, lignes 1, 157.5, 157.9 et 158](https://www.revenuquebec.ca/documents/fr/formulaires/tp/TP-776.42%282025-10%29.pdf).
- Québec : aide sociale imposable (147), indemnités et suppléments déduits au revenu imposable
  (148/295), redressement du montant personnel fourni par le relevé 5 (358/359), crédit de
  cotisations de 10 % (397.1/397). L'annexe F exclut les prestations 147/148 et déduit la partie
  AE des récupérations. Sources :
  [ligne 295](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/276-a-298-2-revenu-imposable/ligne-295/),
  [ligne 358](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/350-a-398-1-credits-dimpot-non-remboursables/ligne-358/),
  [ligne 397](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/350-a-398-1-credits-dimpot-non-remboursables/ligne-397/),
  [annexe F](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.F%282025-12%29.pdf).
- L'adaptateur `ParentIncome.from_tax_return` conserve les retraits REER déplacés et reprend
  l'AE/RQAP et les prestations de remplacement, sans inclure l'aide sociale exclue.
- Aucune clé de formulaire supprimée, aucun alias retiré. Seule la composante REER ordinaire
  change de ligne; la ligne 122 reste disponible pour ses autres revenus.
- Validation de cette étape : 437 tests réussis; sans oracle, 335 réussis et 22 sautés.
  Salarié : 36,512 → 37,596 µs (+3,0 %); retraité : 31,974 → 34,936 µs (+9,3 %).
  Mesure appariée, détails et contrainte historique encore à satisfaire dans `PLAN.md`.
- Ajout de `compute_couple`, `required_couple_questions` et `CoupleReturn` : deux revenus
  calculés avant les crédits, revenu net du conjoint transmis à B/K, droits de B réunis puis
  répartis. Le partage par défaut est égal et peut être choisi explicitement. Les questions
  restent propres à chaque personne; aucun statut ou mois exempté n'est présumé.
  **Change les résultats pour les couples utilisant cette nouvelle API**, puisque les droits
  des deux personnes sont réduits ensemble une seule fois. `compute` conserve ses montants.
  Sources : [annexe B 2025, lignes 23/28/33/34](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.B%282025-12%29.pdf)
  et [guide, ligne 361](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/350-a-398-1-credits-dimpot-non-remboursables/ligne-361/).
- Nouvelles lignes B `1.C`, `8.C`, `9.C` pour la colonne conjoint, sans renommer les clés de la
  colonne du déclarant. `CoupleReturn.refs` relie les déclarations; `Line.refs` reste local.
  Les liens des autres crédits ci-dessous réutilisent ce même contrat.
- Coordination : 469 tests réussis, dont 31 nouveaux; sans données locales, 367 réussis et
  22 sautés. Comparaison exacte de 600 profils et 128 124 montants
  historiques. Salarié : 36,833 → 37,918 µs (1,029×). Aucun paramètre existant modifié.
- Ajout de `CoupleOptions` : confirmations requises pour le montant fédéral pour conjoint,
  son supplément pour infirmité et les transferts fédéraux. Les questions inconnues bloquent
  `compute_couple`; les choix figurent dans son JSON. Ajout de `5000-S5` (30300/30425) et
  `5005-S2` propre au Québec (âge/pension inutilisés vers 32600). Sources :
  [annexe 5](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5000-s5/5000-s5-25f.pdf),
  [annexe 2 du Québec](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s2/5005-s2-25f.pdf),
  [TD1 2026](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/td1/td1-26f.pdf).
- **Change les résultats** : les soldes TP-1:413/430 restent négatifs lorsque des crédits
  sont inutilisés, même pour une personne seule; le plancher zéro est appliqué à 432. Dans
  `compute_couple`, le transfert à 431 réduit l'impôt du bénéficiaire et les grilles 7/8 du
  TP-776.42 recalculent la portion admise à l'IMR; l'annexe E reprend le transfert à 11.
  Le transfert québécois peut être désactivé. Sources :
  [TP-1, lignes 413 à 432](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D%282025-12%29.pdf),
  [ligne 431](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/400-a-447-impot-et-cotisations/ligne-431/),
  [TP-776.42, grille 8](https://www.revenuquebec.ca/documents/fr/formulaires/tp/TP-776.42%282025-10%29.pdf).
- Les transferts d'études/handicap, les autres personnes à charge, l'annexe A et le
  fractionnement restent à compléter. Les documents S2/S5 exposent uniquement les parties
  calculées. Aucune clé existante renommée par ce lot.
- Transferts : 497 tests réussis; copie publique : 395 réussis, 22 sautés. Les 600 totaux
  historiques sont inchangés; huit montants intermédiaires sur 128 124 deviennent négatifs
  (413/430). Aucune des 202 entrées numériques préexistantes des TOML ne change.
- Performance du lot transferts : salarié 37,496 → 39,496 µs (1,053×); maximum 1,092×
  parmi les cinq profils. La cible historique reste ouverte; détails dans `PLAN.md`.
- La portée complète demandée et les éléments encore à faire figurent dans `IMPLEMENTATION.md`.

## 0.5.0 — 2026-10-04

**Change l'API et change les résultats.** La couverture RAMQ annuelle et l'absence de conjoint
ne sont plus présumées. Les paramètres numériques préexistants restent inchangés; les nouveaux
paramètres de ménage et de prorata complètent les tables annuelles.

- `Taxpayer` ajoute `has_spouse`, `spouse_net_income`, `drug_plan_exempt_months` et
  `drug_plan_dependent_children`. Leur valeur par défaut `None` signifie « inconnu ».
  Les mois sont des entiers uniques de 1 à 12; une liste JSON est normalisée en tuple immuable.
- **Migration requise** : appeler `required_questions(tp)` et recueillir les réponses.
  `compute` lève `MissingInformationError` si elles manquent, avec `questions` et `to_dict()`
  pour les présenter à l'utilisateur. Aucun montant ni déclaration partielle n'est rendu.
  L’appel direct à `rules.drug_insurance_premium` exige aussi les arguments nommés
  `has_spouse`, `dependent_children` et `exempt_months`. Pour reproduire le profil historique
  sans conjoint ni enfant, assujetti douze mois,
  fournir explicitement `has_spouse=False`, `drug_plan_exempt_months=()` et
  `drug_plan_dependent_children=0`. Ne pas appliquer ces réponses par défaut aux utilisateurs.
- L'annexe K reprend le revenu net du conjoint, les exemptions pour enfants, le barème
  avec/sans conjoint et les réductions distinctes des deux semestres. Une assurance privée de
  base pendant douze mois donne zéro; chaque conjoint paie uniquement sa cotisation personnelle.
  Source : [annexe K 2025, parties A à C, lignes 36 à 98](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.K%282025-12%29.pdf).
- `has_spouse` est indépendant de `lives_alone` : voir la [définition du conjoint au 31 décembre](https://www.revenuquebec.ca/fr/definitions/conjointe-ou-conjoint-au-31-decembre/).
  Le revenu du conjoint entre aussi dans la réduction de l'annexe B (lignes 12 à 18), selon
  [l'annexe B 2025](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.B%282025-12%29.pdf).
  Les droits du conjoint dans B, leur répartition, les autres crédits et transferts entre
  conjoints restent hors portée et déclenchent un avertissement explicite.
- RAMQ 2026 : les exemptions familiales sont des estimations indexées, les taux et le prorata
  reprennent 2025. Le statut demeure `unpublished`; un avertissement est aussi rendu lorsque
  l'exemption estimée produit zéro. Les couvertures exemptant les douze mois ne consultent pas
  ces paramètres. Sources et méthode d'estimation dans `parametres/2026/quebec.toml`.
- 362 tests réussis, dont 49 nouveaux cas, l'oracle local, la continuité et le revenu net
  croissant; 260 réussis et 22 sautés dans une copie sans oracle. Les profils historiques sont
  explicites, sans changer les valeurs attendues.
  Comparaison exacte supplémentaire : 500 profils fictifs, 92 540 montants et tous les totaux
  inchangés lorsque les anciennes hypothèses sont confirmées.
- Performance : salarié type 35,410 → 36,466 µs (+3,0 %); cinq profils mesurés, surcoût
  maximal 1,036× pour la correction RAMQ. La branche complète atteint 1,55× `main` pour le salarié. Protocole et résultats détaillés dans `PLAN.md`.
- Aucune clé de formulaire ou de ligne renommée. Les alias `federal` et `quebec` sont conservés.

## 0.4.0 — 2026-10-04

**Complète l'API, pas les montants.** Aucun taux, seuil ni montant de paramètre publié ne change.
Aucune clé existante n'est renommée ou supprimée; les alias Python et JSON restent disponibles.
Le retrait des alias JSON initialement annoncé après 0.3 est différé.

- Ajout des formulaires `5000-S3` et `TP-1.D.G` pour le total net de gains en capital fourni et
  son inclusion. Leurs lignes `19900` et `108` alimentent le T1 `12700` et le TP-1 `139`.
  Les dispositions individuelles, catégories de biens et provisions ne sont pas reconstituées.
- Ajout de `5005-S8` (parties 1 et 2) et `TP-1.D.U` (partie B) pour les cotisations RRQ d'un
  salarié québécois de 19 à 72 ans, assujetti toute l'année. Les lignes `P2-35` et `P2-47` de
  l'annexe 8 alimentent le T1 `30800` et `22215`; la ligne `23` de U alimente le TP-1 `248`.
  Les retenues simulées égalent les cotisations requises; aucun trop-perçu n'est inventé.
- Ajout de TP-1 `98.1`, salaire admissible simulé, source des calculs de l'annexe U.
- Les métadonnées 2025/2026, les références et les paramètres cités suivent le modèle de 0.3.
  Seules les parties couvertes sont construites. La construction groupée de l'annexe 8 limite
  le coût des lignes supplémentaires, sans nouvelle dépendance ni classe de formulaire.
- À 18 ans et dès 73 ans, les annexes RRQ sont omises et un avertissement explicite signale
  les limites du calcul annuel hérité. **Aucune correction fiscale n'est appliquée.**
- Tests : cas chiffrés des deux plafonds RRQ, reports exacts, absence des formulaires non
  applicables, métadonnées, références et JSON. Comparaison exacte de 2 049 déclarations
  fictives avec 0.3.0 : 320 044 montants de lignes et tous les totaux inchangés. Suite complète :
  313 tests réussis avec l'oracle local; 211 réussis et 22 sautés sans les relevés locaux.
- Performance : 35,994 µs pour le salarié type, contre 24,414 µs en 0.3.0; surcoût maximal
  mesuré de 1,47× sur les cinq profils. Protocole et résultats détaillés dans `PLAN.md`.

## 0.3.0 — 2026-10-04

**Change l'API, pas les montants.** Aucun fichier de paramètres fiscaux déjà publié n'est modifié.

- `TaxReturn.forms` regroupe les déclarations et les annexes par code officiel. Chaque annexe
  est calculée par une fonction distincte; les documents non applicables ne sont pas construits.
  `federal` et `quebec` restent des alias vers les mêmes objets `T1` et `TP-1`.
- `Form` expose `code`, `title`, `version`, `source` et `lines`. Les métadonnées proviennent des
  nouveaux `parametres/AAAA/formulaires.toml`, validés au chargement. Les formulaires fiscaux
  2026 utilisent la numérotation des PDF 2025 (`rule_2025`).
- `Line.refs` décrit les dépendances entre lignes; `Line.params` identifie les paramètres et
  leurs sources. `Line` reste immuable et devient un `NamedTuple` pour limiter le coût de
  construction des annexes; les quatre arguments historiques restent valides.
- `TaxReturn.to_dict()` ajoute `forms` avec métadonnées et lignes. Les clés `federal` et `quebec`
  sont conservées **pendant la version 0.3**, sous leur forme de dictionnaires de lignes.
  `Form.to_dict()` rend désormais les métadonnées et `lines` au lieu des seules lignes.
  `Form(code=...)` remplace `Form(name=...)`; `name` reste un alias en lecture de `code`.
- `ChildSupportResult.form` utilise le code `FIXATION-PA` et le document officiel version
  `2016-01`. Son JSON inclut le code, les métadonnées et `lines`.
- Validation : tests existants conservés (seuls les accès aux anciennes clés ci-dessous sont
  adaptés), tests de provenance et de références, reports des annexes, JSON, applicabilité,
  et comparaison exacte de 2 005 déclarations fictives avec 0.2.0. Mesures dans `PLAN.md`.

| Ancien accès | Nouvel accès |
| --- | --- |
| `r.federal["T691:93"]` | `r.forms["T691"]["P1-93"]` |
| `r.federal["T691:95"]` | `r.forms["T691"]["P1-95"]` |
| `r.federal["T691:103"]` | `r.forms["T691"]["P1-103"]` |
| `r.quebec["E:15"]` | `r.forms["TP-1.D.E"]["15"]` |
| `r.quebec["TP-776.42:rajuste"]` | `r.forms["TP-776.42"]["22"]` |

Les lignes du TP-1 361, 446, 447 et 391 conservent leurs montants et référencent respectivement
les lignes B:34, F:82, K:98 et TP-752.PC:50. Les sources officielles des numéros et des titres
sont les PDF cités dans les catalogues annuels. Cette refonte préserve les règles fiscales de
0.2.0, y compris leurs limites; elle ne constitue pas une correction fiscale.

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
