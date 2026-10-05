<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Couverture fiscale complète demandée le 4 octobre 2026

Objectif : implémenter tous les éléments recensés dans la conversation, pour les résidents du
Québec (fédéral et Québec). Ce registre conserve la portée entière; une étape intermédiaire ou
un test vert ne vaut pas achèvement du projet. Les crédits historiques abolis et ceux réservés
aux autres provinces ne sont pas à réintroduire pour 2025/2026.

## Conditions de livraison

- [ ] Chaque cas pris en charge a ses entrées explicites, ses questions d'admissibilité et ses règles officielles.
- [ ] Chaque document applicable est un Form générique, avec lignes officielles, refs et params.
- [ ] Paramètres et métadonnées annuels sourcés; valeurs existantes inchangées, corrections de formules documentées.
- [ ] Tests chiffrés indépendants, frontières d'admissibilité, interactions entre formulaires, JSON et références.
- [ ] Tests historiques, validation locale, continuité et revenu disponible; exceptions légales explicites aux propriétés générales.
- [ ] Mesure avant/après et mode rapide sans duplication des règles fiscales.
- [ ] README, PLAN, CHANGELOG et demande de fusion décrivent la portée réellement vérifiée.

## Éléments à vérifier individuellement

| ID | Élément | État / preuve |
| --- | --- | --- |
| R01 | RPA, rentes REER, FERR admissibles, revenus de survivant; crédits de pension | Implémenté : 5000-D1/31400, T1, TP-1/B; tests/test_revenus_prestations.py |
| R02 | AE régulière/spéciale et RQAP, remboursement AE et interaction PSV | Implémenté pour prestations et trop-perçus déduits cette année; choix rétroactif/crédits de remboursement à compléter |
| R03 | SRG reçu, aide sociale, indemnités et redressement québécois | Implémenté à partir des relevés; redressement RL-5/TP-752.0.0.6 fourni, attribution familiale explicite |
| D01 | Cotisations RPA et cotisations syndicales/professionnelles distinctes fédéral/Québec | Implémenté : 20700/21200, 205/397.1/397; tests/test_revenus_prestations.py |
| D02 | REER : annexe 7, plafond, cotisations datées/inutilisées, RAP/REEP et reports | À implémenter |
| D03 | CELIAPP : annexe 15, droits, cotisations, transferts et retraits | À implémenter |
| D04 | Intérêts/frais financiers, annexe N, rajustements et reports | À implémenter |
| Q01 | Questionnaire familial : dates/statuts, vivre seul, personnes à charge et garde partagée | À implémenter |
| Q02 | Deux déclarations coordonnées; crédits conjoint/personnes à charge, annexes 2/5/A | Revenus/RAMQ, S5 conjoint, S2 âge/pension et TP-1:431 implémentés; autres personnes à charge, études, handicap et annexe A à compléter |
| Q03 | Annexe B : droits du conjoint, répartition, supplément monoparental | Droits des deux conjoints et partage implémentés; supplément monoparental et admissibilité détaillée à compléter |
| Q04 | T1032 et annexe Q : fractionnement, revenus admissibles, choix distincts par régime | RPA/rentes REER/FERR implémentés, prorata, crédits et retenues compris; conventions de retraite, vétérans, RPAC, pensions étrangères et exclusions de transferts directs à compléter |
| Q05 | Annexe K : détermination des exemptions mensuelles et paiement de la prime du conjoint | À implémenter |
| C01 | RRQ : choix de cessation, prorata à 18 ans, arrêt après 72 ans, retenues/trop-perçus réels | À implémenter |
| C02 | AE/RQAP : assujettissement, retenues réelles, annexes 10/13/R selon le cas; emploi hors Québec | À implémenter |
| C03 | Crédit carrière TP-752.PC : revenus autonomes et ajustements admissibles | À implémenter |
| F01 | Frais de garde : T778 et annexe C, admissibilité et répartition | À implémenter |
| F02 | Frais médicaux fédéraux et annexe B C/D; choix de période et de demandeur | À implémenter |
| F03 | Dons : annexes 9/V, reports et interactions IMR | À implémenter |
| F04 | Études : annexes 11/M/S/T, intérêts, formation, transferts et reports | À implémenter |
| F05 | Handicap, transferts et produits/services de soutien; admissibilité attestée | À implémenter |
| F06 | Aidants : crédit canadien et annexe H | Conjoint soutenu fédéral 30300/30425 implémenté; autres personnes à charge et annexe H à faire |
| F07 | Maintien à domicile : annexe J; frais d'autonomie de l'annexe B | À implémenter |
| F08 | Activités sportives/artistiques/culturelles des enfants au Québec | À implémenter |
| F09 | Achat d'habitation fédéral et TP-752.HA | À implémenter |
| F10 | Accessibilité domiciliaire et annexe fédérale 12 (rénovation multigénérationnelle) | À implémenter |
| F11 | Pompiers et recherche-sauvetage volontaires | À implémenter |
| F12 | Contributions politiques fédérales et municipales québécoises | À implémenter; Québec : 2025 seulement, abolition dès 2026 |
| F13 | Régions éloignées : T2222 / TP-350.1 | À implémenter |
| F14 | Soutien aux aînés : TP-1029.SA, ligne 463 et partage entre conjoints | À implémenter |
| B01 | Allocation canadienne pour travailleurs (annexe 6), prime au travail (P), solidarité (D) | À implémenter |
| B02 | ACE, Allocation famille, TPS/TVH puis ACEBE dès juillet 2026 : périodes de versement et garde | À implémenter |
| B03 | Bouclier fiscal : TP-1029.BF, hausse de revenus et perte de transferts | À implémenter pour 2025; aboli dès 2026 |
| I01 | Dispositions détaillées (annexes 3/G), PBR, dépenses, provisions, pertes et reports | À implémenter |
| I02 | Revenus étrangers, conversions et crédits T2209 / TP-772 | À implémenter |
| I03 | IMR : bases négatives et ajouts exacts, reports sur sept ans T691 / TP-776.42 / E | Bases signées, rajouts et transferts québécois (grille 8) implémentés dans la portée présente; reports et interactions des futurs crédits à faire |
| E01 | Location : T776 / TP-128, dépenses, quote-parts et amortissement | À implémenter |
| E02 | Entreprises : T2125 / TP-80 / L, dépenses, amortissement, cotisations autonome | À implémenter |
| E03 | Dépenses d'emploi : T777 / TP-59, conditions et remboursements | À implémenter |
| P01 | FIXATION-PA : revenu de l'enfant, ajustements motivés, entente, difficultés excessives | À implémenter; appréciations judiciaires à saisir explicitement |
| A01 | Retenues T4/RL-1, acomptes, trop-perçus : solde/remboursement réel | Retenues d’impôt et acomptes confirmés via TaxPayments, transferts et soldes implémentés; trop-perçus de cotisations, transferts interprovinciaux et transferts de remboursement à compléter |
| A02 | Économie REER, taux marginal par revenu et effet sur le revenu disponible | À implémenter |
| A03 | Mode rapide pour retraiteqc, même calcul que les documents, intégration et mesure | À implémenter |
| A04 | Plusieurs exemplaires d'un document pour plusieurs entreprises/immeubles/pays | À implémenter sans perdre les alias des formulaires principaux |

## Point de départ vérifié

- Branche `codex/couverture-fiscale-complete`, issue de `main` 226de1f.
- Worktree isolé existant réutilisé; modifications du checkout principal conservées intactes.
- 362 tests passent, relevés locaux compris.
- Python 3.14.3, médiane de 7 × 10 000 appels, paramètres chauds : salarié 37,888 µs;
  retraité 32,288 µs; carrière 43,889 µs; gain en capital 42,403 µs; sans revenu 20,042 µs.
- La mesure de la version 0.3 est conservée dans PLAN.md; ne pas déplacer la référence historique
  de performance en ajoutant successivement des fonctionnalités.


## Comparaison avec la liste fournie : portée Québec

Inventaire vérifié sur `main` 226de1f (version 0.5.0), puis recoupé avec les sources
publiques le 4 octobre 2026. Les nouvelles entrées d'API en cours de travail ne sont pas
comptées comme des calculs disponibles avant leur intégration et leur validation.

Les annexes québécoises B, E, F, G, K et U existent, mais ne couvrent que les parties
décrites dans README.md. Quatorze annexes de la trousse TP-1 sont encore absentes :

| Annexes Québec | Ajout attendu | Rapprochement fédéral, avec règles distinctes |
| --- | --- | --- |
| A, S | Personnes à charge et transferts liés aux études | Annexes 5 et 11 |
| C | Frais de garde admissibles et crédit familial | Déduction T778 |
| D | Solidarité, logement et renseignements familiaux | Prestations calculées séparément de la T1 |
| H | Personnes aidantes et personnes aidées | Crédit canadien pour aidant, annexe 5 |
| J | Services admissibles de maintien à domicile des aînés | Pas d'annexe fédérale directement équivalente |
| L | Revenus nets des entreprises, reliés aux TP-80 | T2125 |
| M, T | Intérêts étudiants, frais d'études et reports | Annexe 11 et intérêts sur prêts étudiants |
| N | Limitation et report des frais de placement | Déduction des frais financiers au T1 |
| P | Primes au travail | Allocation canadienne pour les travailleurs, annexe 6 propre au Québec |
| Q | Transfert de revenus de retraite entre conjoints | Choix T1032 |
| R | RQAP des situations particulières | Annexes 10/13 selon l'assujettissement AE/RQAP |
| V | Dons admissibles et reports | Annexe 9 |

Sources des deux trousses :
- [Revenu Québec, TP-1 et annexes 2025](https://www.revenuquebec.ca/fr/services-en-ligne/formulaires-et-publications/details-courant/tp-1/).
- [ARC, trousse fédérale 2025 pour le Québec](https://www.canada.ca/fr/agence-revenu/services/formulaires-publications/trousses-impot-toutes-annees-imposition/trousse-generale-impot-prestations/quebec.html).

Autres documents manquants : T776/TP-128 (location), T777/TP-59 (dépenses d'emploi),
T2209/TP-772 (impôt étranger), T2222/TP-350.1 (régions éloignées), TP-752.HA (achat
d'habitation), annexes fédérales 7/15 (REER/CELIAPP) et 12 (habitation multigénérationnelle).
Les crédits sans annexe autonome doivent utiliser leur grille officielle ou la T1/TP-1;
il ne faut pas inventer de codes de formulaires pour chaque option.

### Différences annuelles vérifiées

- Québec : le Bouclier fiscal et le crédit pour contributions politiques municipales
  s'appliquent à 2025, puis sont abolis dès 2026. La variante annuelle doit désactiver
  ces règles sans changer les paramètres publiés de 2025.
  Source : [Budget du Québec 2025-2026, plan budgétaire, D.35](https://www.finances.gouv.qc.ca/Budget_et_mise_a_jour/budget/documents/Budget2526_PlanBudgetaire.pdf).
- La hausse proposée du taux d'inclusion des gains en capital mentionnée dans l'image
  a été annulée. Ne pas introduire un passage automatique aux deux tiers en 2026.
  Source : [Budget fédéral 2025, annexe 1, tableau A1.18 et note 3](https://www.budget.canada.ca/2025/report-rapport/anx1-fr.html).
- Le crédit fédéral pour abonnements aux nouvelles numériques se termine avec 2024;
  il n'est pas à ajouter aux années 2025/2026.
  Source : [ARC, ligne 31350](https://www.canada.ca/fr/agence-revenu/services/impot/particuliers/sujets/tout-votre-declaration-revenus/declaration-revenus/remplir-declaration-revenus/deductions-credits-depenses/ligne-31350-depenses-pour-abonnement-aux-nouvelles-numeriques.html).
- RRQ : l'option de cessation vise les bénéficiaires admissibles à partir de 65 ans;
  l'arrêt automatique commence le 1er janvier suivant le 72e anniversaire. Ne pas
  transposer la borne de 70 ans du RPC figurant dans l'image.
  Source : [Retraite Québec, choix de cessation](https://www.retraitequebec.gouv.qc.ca/fr/citoyens/travail/travail-et-retraite/choisir-arreter-cotiser-regime-rentes-quebec).
- Les activités physiques, artistiques, culturelles ou récréatives des enfants ont un
  crédit québécois propre, avec admissibilité et plafond de revenu familial à demander.
  Source : [Revenu Québec, activités des enfants](https://www.revenuquebec.ca/fr/citoyens/credits-dimpot/credit-dimpot-pour-activites-des-enfants/).
- Pour le module de prestations : l'ACEBE remplace le crédit TPS/TVH dès juillet 2026.
  L'année fiscale de référence et la période des paiements sont des données distinctes;
  ne pas utiliser le seul champ `year` pour les deux.
  Source : [ARC, ACEBE](https://www.canada.ca/fr/agence-revenu/services/prestations-enfants-familles/allocation-canadienne-epicerie-besoins-essentiels.html).

### Ordre de travail proposé

1. Revenus/déductions et questionnaire familial, puis coordination des conjoints.
2. Retraite et fractionnement, frais de garde/médicaux, crédits remboursables fréquents.
3. Dons, études, handicap et autres crédits; reports et interactions avec l'IMR.
4. Location, entreprises et dépenses détaillées, puis comparaisons et intégration rapide.

Les priorités ordonnent la réalisation et ne retranchent aucun élément du registre.


## Étape revenus/déductions validée

- Entrées raccordées au moteur : `PensionIncome`, `Benefits`, `Deductions`; questions bloquantes.
- Feuille 5000-D1 et traitements distincts fédéral/Québec, avec refs/params vérifiés.
- Corrections documentées : REER ordinaire à TP-1:154, bases signées d'IMR, déduction pour
  travailleur rajoutée à l'IMR québécois. Aucun nombre préexistant des TOML n'a changé.
- 437 tests passent; copie sans données locales : 335 passent, 22 sautés.
- Performance mesurée avant/après : salaire 36,512 → 37,596 µs; retraite 31,974 → 34,936 µs.
  La cible globale historique reste ouverte (salarié 1,60× la référence 0.3).
- Prochaine étape : Q01/Q02/Q03, questionnaire familial et déclarations coordonnées, puis Q04.
  Le registre complet conserve les autres formulaires à implémenter; cette étape ne le clôt pas.


## Étape coordination des conjoints et annexe B

- `compute_couple` calcule d'abord les deux revenus, puis les crédits, dans les mêmes objets
  Form. Aucun revenu du conjoint présumé nul ni déclaration provisoire n'est construit.
- B : montants communs des deux personnes, une seule réduction familiale, partage explicite
  (50 % par défaut); RAMQ : revenus automatiquement croisés, chaque personne paie sa prime.
- Références interpersonnelles dans `CoupleReturn.refs`; références locales inchangées.
- Cette étape ne clôt pas Q02/Q03. Le lot suivant ajoute les parties conjoint des annexes 2/5
  et TP-1:431; l'annexe A, le supplément monoparental et le fractionnement restent à calculer.
- 469 tests réussis (dont 31 nouveaux cas de couples); sans données locales, 367 réussis et
  22 sautés. 600 profils historiques, 128 124 montants et tous les totaux
  de `compute` strictement identiques au commit 91050c9. Aucun paramètre numérique changé.
- Performance du calcul individuel : salarié 36,833 → 37,918 µs (1,029×). La cible historique
  reste ouverte; protocole et cinq profils dans PLAN.md.


## Étape crédits et transferts entre conjoints

- `CoupleOptions` et questions bloquantes : demandeur du montant pour conjoint, supplément
  pour infirmité et conditions de transfert fédéral; aucune admissibilité déduite du revenu.
- 5000-S5 : sections 30300/30425 du conjoint soutenu. 5005-S2 : droits d'âge et de pension
  inutilisés, utilisation préalable des crédits propres du conjoint. Les autres sections,
  études et handicap sont encore dans F04/F05/F06 et Q02.
- TP-1 : soldes négatifs conservés à 413/430, transfert à 431; annexe E et grille 8 du
  TP-776.42 pour l'IMR. Les attributions d'études/dons et reports restent dans I03.
- 497 tests passent; sans données locales : 395 passent et 22 sont sautés. Comparaison de
  600 profils avec adb1d3c : tous les totaux inchangés, 128 124 lignes comparées, huit soldes
  intermédiaires changés (413/430) conformément au formulaire; 202 entrées numériques
  préexistantes des TOML strictement conservées.
- Mesure avant/après dans PLAN.md; la contrainte historique de performance reste ouverte.
- Q02 n'est pas clos. Prochaines étapes : questionnaire familial, fractionnement T1032/Q,
  puis frais/crédits familiaux, selon le registre intégral.


## Étape fractionnement des pensions et retenues (5 octobre 2026)

- `PensionSplit` choisit explicitement le cédant, le montant et les confirmations propres à
  chaque régime. T1032 dans les deux déclarations; annexe Q chez le cédant seulement.
- T1032 : plafond, mois d'union/année fiscale, crédit du bénéficiaire de moins de 65 ans et
  décès à l'origine des pensions. Q : cédant de 65 ans ou plus, choix indépendant du fédéral.
- Le transfert précède revenus nets, récupérations AE/PSV et droits familiaux. B inclut
  123 et déduit 245; F déduit le transfert à 46. Les deux bases d'IMR en tiennent compte.
- Retenues de pension transférées dans la proportion prescrite. `TaxPayments` porte les
  quatre montants réels de retenues et d'acomptes; aucun solde ne suppose des paiements nuls.
  Les soldes signés et les lignes de remboursement sont distincts de `total_payable`.
- 546 tests réussis, dont 49 nouveaux; sans données locales : 444 réussis et 22 sautés.
  600 profils historiques comparés à 9811dc2 : 128 124 montants et tous les totaux strictement
  identiques; 1 698 valeurs numériques préexistantes des TOML (tables de pension alimentaire comprises) inchangées.
- Performance : salarié 39,951 → 39,857 µs; maximum 1,059× sur les cinq profils. La cible
  historique reste ouverte à 1,694× pour le salarié; détails dans PLAN.md.
- Q04 et A01 restent partiels. Les pensions particulières et exclusions de revenus doivent
  être ajoutées avec leurs entrées; le prorata T1032 au décès ne représente pas à lui seul
  toutes les règles d'une déclaration de décès. Q01 conserve ce travail.
