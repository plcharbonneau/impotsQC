# Plan — impotsqc

Arbitré par PL le 2026-10-04 :
- fédéral + Québec;
- salarié et retraité dès la v0.1;
- appel direct depuis `retraiteqc`;
- AGPL, GitHub public à terme.

## Ce que la librairie rend

`compute(Taxpayer) -> TaxReturn`. Pour chaque juridiction, `TaxReturn` donne un dictionnaire de
lignes indexé par **numéro officiel**. Chaque `Line` porte :
- `number`, `label` (libellé officiel), `amount`;
- `rule` : la formule appliquée, en une phrase;
- `source` : document officiel et ligne du formulaire.

Les annexes ont leurs propres lignes, nommées `"<annexe>:<ligne>"`. `to_dict()` sérialise le tout
en JSON pour un agent. Les entrées sont des montants annuels d'un contribuable fictif.

## Années

**Un dossier par année, oui — pour les données, pas pour le code.**

```
src/impotsqc/parametres/2026/federal.toml      paliers, montants, taux, seuils (+ source par valeur)
src/impotsqc/parametres/2026/quebec.toml
src/impotsqc/parametres/2026/cotisations.toml  RRQ, AE, RQAP, FSS, RAMQ
oracle/2026/cas.json                           relevés d'un oracle externe (local, ignoré par git)
```

- **Ce qui change chaque année** — taux, seuils indexés, montants de crédit, plafonds,
  maximums des gains assurables — vit dans les TOML. Ajouter 2027 = copier le dossier 2026,
  mettre à jour chaque valeur avec sa nouvelle source, refaire les relevés de l'oracle (locaux).
- **Ce qui change rarement** — la forme d'une règle (nouveau crédit, taux d'inclusion à deux
  paliers, refonte d'une annexe) — est une variante de fonction, choisie par une clé du TOML de
  l'année (p. ex. `inclusion_gains = "unique"`). Une seule implémentation par variante.
- Copier un module entier par année multiplierait les endroits où corriger un bogue :
  c'est exclu.
- **Une année publiée ne bouge plus.** Les tests figent ses cas de validation.

## Performance : la contrainte vient de `retraiteqc`

Mesure du 2026-10-04 sur `retraiteqc` 0.2.1, avec un plan type et 500 chemins :
- 0,31 s au total;
- **861 calculs d'impôt par chemin**;
- 0,51 µs par calcul;
- l'impôt pèse déjà **71 % du temps**.

Ces appels viennent des bissections à 40 pas (retrait REER brut pour un net visé, vente non
enregistrée, meltdown).

Un calcul complet du T1 et du TP-1 en Python coûtera beaucoup plus que la formule actuelle,
estimé de 30 à 60 fois, à mesurer au premier prototype. Branché tel quel, il ralentirait
`retraiteqc` d'un facteur 20 à 40. Leviers, dans l'ordre :

1. **Algorithme, dans `retraiteqc`.** L'impôt est linéaire par morceaux dans le montant retiré.
   Une recherche de racine qui en profite (sécante bornée de type Illinois) converge en environ
   4 appels au lieu de 40, soit environ 10 fois moins d'appels. Les résultats changent au
   millionième de dollar près. Ce passage se fait donc avec le changement de système fiscal, qui
   change déjà les niveaux. Le chemin hérité (`QC_2026` + bissection) reste pour l'oracle.
2. **Mode rapide, dans `impotsqc`.** Mêmes fonctions de calcul, mais sans construire les objets
   `Line` : `total_tax(taxpayer) -> float`. Il n'y a qu'un seul code; un test vérifie que
   `total_tax == compute(...).total_payable` sur tous les cas.
3. **Rust ou table précompilée** : seulement si, après 1 et 2, la mesure montre que l'impôt
   reste le goulot. L'implémentation Python demeure l'oracle de l'accélérateur.

## Étapes

1. **Socle** (fait le 2026-10-04) : dépôt, licence, consignes, squelette du paquet.
2. **Paramètres 2026** (fait le 2026-10-04) : trois TOML, chaque table avec sa source
   officielle, sa référence et son statut, vérifiés à la lecture. Ils reproduisent l'oracle
   externe au dollar près sur toutes les lignes qu'il expose, sauf le maximum RAMQ 2026 (voir les
   points d'interprétation). Trois tables restent provisoires : prolongation de carrière, IMR du
   Québec, et taux et exemptions de l'assurance médicaments.
3. **Calcul v0.1** (terminé le 2026-10-04 : `compute(Taxpayer) -> TaxReturn`, environ 25 µs par déclaration), ligne par ligne :
   - **T1** : revenus (emploi, pensions, PSV, RRQ, REER, dividendes majorés, intérêts, gains en
     capital imposables), déductions (REER, RRQ bonifiée, remboursement des prestations),
     revenu net et imposable, crédits non remboursables (personnel de base réduit en haut de
     l'échelle, âge, pension, emploi, cotisations), crédit pour dividendes, abattement du Québec,
     récupération de la PSV, impôt minimum de remplacement.
   - **TP-1** : revenus, déduction pour travailleur, déduction REER, revenu net et imposable,
     montant de base, allègements de l'annexe B (âge, personne vivant seule, revenu de
     retraite, réduits selon le revenu familial), prolongation de carrière, crédit pour
     dividendes, impôt minimum, cotisation RAMQ, contribution au FSS.
   - **Cotisations du salarié** : RRQ (base et bonifiée), AE (taux du Québec), RQAP.
   - **Impôt minimum de remplacement** : T691 au fédéral (concordance exacte avec l'oracle);
     annexe E et TP-776.42 au Québec, calculés par analogie avec le fédéral à partir des
     paramètres officiels (le formulaire TP-776.42 n'a pas pu être lu). Le report sur sept ans
     n'est pas modélisé; un avertissement l'indique.
   - Numéros d'annexes et de lignes : repris des formulaires officiels (versions 2025 tant que
     2026 n'est pas publié), jamais de mémoire.
4. **Validation** (faite le 2026-10-04) : 32 cas fictifs ligne par ligne contre un oracle externe,
   **pour 2025 et 2026**. Il reste deux écarts, les deux points d'interprétation ci-dessous,
   déclarés dans les relevés de l'oracle et vérifiés à leur valeur exacte.

   2025 a été ajouté sans changer une ligne de code : seuls les paramètres diffèrent.
5. **Intégration `retraiteqc`** : un `TaxSystem` adossé à `impotsqc`, neutre par défaut (le
   test d'oracle de `retraiteqc` reste à l'égalité exacte), plus le levier 1. Mesure du temps
   de simulation avant et après. Puis re-mesure appariée des verdicts qui en dépendent.

## Pension alimentaire pour enfants (0.2.0)

Module `child_support`, ajouté à la demande de PL le 2026-10-04 : le formulaire de fixation du
modèle québécois, avec les tables annuelles (`parametres/AAAA/pension_alimentaire.toml`). Prochaine
validation possible : l'outil de calcul en ligne du ministère de la Justice, qui demande de soumettre
un formulaire web (à faire avec l'accord de PL). Hors portée : ajustements motivés (512.1, 518.1,
526.1, 534.1, 564.1), partie 7 (entente), difficultés excessives, revenu de l'enfant.

## Points d'interprétation

Deux règles où impotsqc suit sa lecture du formulaire officiel et où un calculateur externe
diverge. Chacune est à confirmer par un logiciel certifié par Revenu Québec.

1. **Retraits REER et montant pour revenus de retraite (annexe B).** Le guide du TP-1 inscrit à
   la ligne 122 « les prestations d'un régime enregistré d'épargne-retraite (REER) », avec les
   FERR et les rentes. L'annexe B calcule le montant sur les lignes 122 et 123 sans condition
   d'âge; le guide, ligne 361, n'exclut que la PSV, les rentes du RRQ et du RPC, et la convention
   de retraite. impotsqc inclut donc les retraits REER. Effet : jusqu'à environ 370 $ d'impôt du
   Québec en moins par année. Cas décisif : 66 ans, retrait REER de 60 000 $, PSV de 8 900 $,
   année 2025. impotsqc donne 2 349 $ à la ligne 361.
2. **Maximum de la cotisation au régime d'assurance médicaments 2026 (annexe K).** Le maximum de
   l'année est la somme de six mois à chacun des deux tarifs mensuels, arrondie au dollar. C'est
   la règle de l'annexe K 2025 : 6 × 62,00 + 6 × 63,83 = 754,98 $, imprimé 755 $. Avec la prime
   de 789 $ annoncée par la RAMQ le 2026-06-30, cela donne 777 $ pour 2026. Valeur provisoire
   jusqu'à l'annexe K 2026. En 2025, l'oracle et impotsqc donnent tous deux 755 $.
3. **Impôt minimum du Québec.** Taux de 19 %, exemption indexée, gains en capital à 100 % et 50 %
   des crédits non remboursables : bulletin d'information 2023-4 de Finances Québec et Chaire en
   fiscalité et en finances publiques. Le détail des déductions rajoutées est calqué sur le T691;
   à vérifier sur le TP-776.42.

## Hors portée de la v0.1

Travail autonome, couple et fractionnement du revenu de pension, transferts entre conjoints,
enfants et crédits remboursables (solidarité, allocation famille), frais médicaux, dons,
acomptes provisionnels, pertes reportées, résidents d'une autre province.
