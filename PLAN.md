# Plan — impotsqc

Arbitré par PL le 2026-10-04 :
- fédéral + Québec;
- salarié et retraité dès la v0.1;
- appel direct depuis `retraiteqc`;
- AGPL, GitHub public à terme.

## Ce que la librairie rend

`compute(Taxpayer) -> TaxReturn`. `TaxReturn.forms` contient un objet `Form` par déclaration
ou annexe applicable, sous son code officiel. `r.federal` et `r.quebec` sont des alias de `T1`
et `TP-1`. Une fonction par annexe remplit le même type générique `Form` : aucune classe propre
à un formulaire et aucun attribut Python propre à un numéro de ligne.

Chaque `Form` expose `code`, `title`, `version`, `source` et `lines`. Chaque `Line` immuable porte :
- `number`, `label`, `amount`, `rule`;
- `refs`, les liens vers les lignes sources au format `CODE:ligne`;
- `params`, les clés `fichier.table.clé` dont la table porte la source officielle.

Les clés de lignes sont les numéros officiels 2025. Le T691 utilise `P1-93`, `P5-11`, etc.,
car sa numérotation recommence à chaque partie. Le TP-776.42 utilise `22` pour le revenu
imposable modifié. `to_dict()` rend les métadonnées et les lignes dans `forms`; les anciens
conteneurs JSON `federal` et `quebec` restent conservés en 0.4; leur retrait est différé.

Les métadonnées sont des données annuelles dans `formulaires.toml`. Les documents de 2025 sont
encore utilisés pour 2026 (`rule_2025`), sans modifier les taux et seuils de 2026. Le document
`FIXATION-PA` porte la version imprimée `2016-01`, commune aux deux années livrées.

## Années

**Un dossier par année, oui — pour les données, pas pour le code.**

```
src/impotsqc/parametres/2026/federal.toml      paliers, montants, taux, seuils (+ source par valeur)
src/impotsqc/parametres/2026/quebec.toml
src/impotsqc/parametres/2026/cotisations.toml  RRQ, AE, RQAP
src/impotsqc/parametres/2026/formulaires.toml  titres, versions, PDF officiels, références et statuts
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
     annexe E et TP-776.42 au Québec. La refonte 0.3 expose les étapes dans les documents
     officiels sans changer les règles numériques héritées de 0.2. Le report sur sept ans
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

## Extraction des formulaires (0.3.0)

Implémentée le 2026-10-04 à partir de `main` (`0cbe38e`). Les fonctions des modules
`federal_schedules` et `quebec_schedules` remplissent les annexes avant que leur résultat soit
repris dans le T1 ou le TP-1. Les liens rendent les dépendances lisibles, sans moteur de graphe
ni résolution dynamique dans le chemin de calcul.

Les formulaires absents ne sont pas construits. Une annexe présente expose seulement les parties
utiles et couvertes par le moteur : pas de report d'IMR fictif, pas de conjoint fictif. La partie 6
du T691 est omise lorsque l'impôt ordinaire domine; les grilles sans ajouts ou réductions du
TP-776.42 et la grille de la RAMQ dont le plafond est atteint sont omises.

Vérifications : 278 tests réussis avec les relevés locaux; 2 005 déclarations fictives comparées
ligne par ligne à la version 0.2.0, **aucun écart exact**, y compris les cinq clés déplacées et
le total à payer. Les tests de continuité et de revenu net croissant restent inchangés.

Mesure `timeit` sur Python 3.14.3, entrées préconstruites et paramètres chargés, médiane de
7 répétitions de 10 000 appels. Le coût inclut tous les objets rendus par `compute()`, sans
sérialisation JSON. Les temps dépendent de la machine; le script est reproductible :

```bash
PYTHONPATH=src python benchmarks/compute.py
```

| Profil fictif, année 2026 | 0.2.0 (µs) | 0.3.0 (µs) | Rapport |
| --- | ---: | ---: | ---: |
| Salarié, 40 ans, emploi de 80 000 $ | 24,837 | 24,327 | 0,98× |
| Retraité, 66 ans, FERR 30 000 $, PSV 9 000 $, RRQ 12 000 $ | 25,184 | 32,252 | 1,28× |
| Prolongation de carrière, 67 ans, emploi de 45 000 $ | 25,225 | 31,662 | 1,26× |
| IMR, 50 ans, gain en capital de 600 000 $ | 26,691 | 39,692 | 1,49× |
| Sans revenu, 40 ans | 24,092 | 20,232 | 0,84× |

L'ajout de `refs` et `params` à la dataclass gelée initiale dépassait le budget de performance.
`Line` utilise donc un tuple nommé immuable, qui réduit le coût mesuré de construction, sans
nouvelle dépendance. Les calculs ne font pas de recherche de métadonnées par ligne.

## Formulaires complémentaires (0.4.0)

La suite de la refonte part de `main` après la fusion de la demande de fusion nº 1 (`2b768a2`).
Elle expose quatre documents supplémentaires à partir des entrées déjà présentes dans `Taxpayer` :

| Formulaire | Partie couverte | Ligne reprise par la déclaration |
| --- | --- | --- |
| `5000-S3` | Total net fourni et inclusion, fin de la partie 4 et partie 5 | `19900` → T1 `12700` |
| `TP-1.D.G` | Partie F, du gain net fourni à l'inclusion | `108` → TP-1 `139` |
| `5005-S8` | Parties 1 et 2, salarié québécois, retenues simulées égales aux cotisations requises | `P2-35` → T1 `30800`; `P2-47` → T1 `22215` |
| `TP-1.D.U` | Partie B, déduction RRQ du salarié | `23` → TP-1 `248` |

Les sources sont les PDF officiels 2025 référencés dans les catalogues annuels. Le gain net
est une entrée agrégée : aucune catégorie de bien, transaction, provision, date ni prix de base
n'est inventé. Les parties 3/G exposées commencent respectivement à `19700` et `94.1`.

Les annexes RRQ concernent uniquement les profils annuels de 19 à 72 ans. Les retenues sont
celles de la règle commune `qpp_contributions`, déjà utilisée par 0.3.0; les montants transférés
restent identiques bit pour bit. Les différences nulles de l'annexe 8 sont résumées à `P2-24`,
avec des références vers les retenues et cotisations requises. Les lignes auxiliaires servant
uniquement à répartir un excédent ou un manque ne sont pas construites.

À 18 ans, le mois de naissance nécessaire au prorata manque. Dès 73 ans, la cessation des
cotisations n'est pas gérée dans le moteur hérité. Les deux situations reçoivent un avertissement,
et les annexes 8/U ne sont pas produites. Les montants historiques sont conservés : traiter ces
limites demanderait une correction fiscale distincte et une entrée « change les résultats ».

Vérification numérique : 2 049 déclarations fictives comparées à 0.3.0, y compris les voisinages
des deux plafonds RRQ et l'exemption. Les 320 044 montants de lignes préexistantes et tous les
totaux sont strictement identiques. Aucun fichier de paramètres fiscaux n'est modifié; seules
quatre tables sont ajoutées à chacun des catalogues de formulaires.

Validation finale : **313 tests réussis** avec l'oracle local et les exemples exécutables;
**211 réussis, 22 sautés** dans une copie sans `oracle/`. Les tests de continuité et de revenu net
croissant sont conservés, ainsi que toutes les valeurs attendues des tests fiscaux existants.

Mesure finale appariée avec `timeit` et `benchmarks/compute.py`, Python 3.14.3 : `main` 0.3.0 et
la branche 0.4.0 dans le même environnement, paramètres chauds, contribuables préconstruits,
médiane de 7 répétitions de 10 000 appels, sans JSON.

| Profil fictif, année 2026 | 0.3.0 (µs) | 0.4.0 (µs) | Rapport |
| --- | ---: | ---: | ---: |
| Salarié, 40 ans, emploi de 80 000 $ | 24,414 | 35,994 | 1,47× |
| Retraité, 66 ans, FERR 30 000 $, PSV 9 000 $, RRQ 12 000 $ | 33,038 | 31,262 | 0,95× |
| Prolongation de carrière, 67 ans, emploi de 45 000 $ | 31,551 | 43,621 | 1,38× |
| IMR, 50 ans, gain en capital de 600 000 $ | 38,852 | 42,051 | 1,08× |
| Sans revenu, 40 ans | 20,696 | 20,135 | 0,97× |

Le surcoût maximal de cette mesure est de **1,47×**. Les annexes RRQ construisent leurs lignes
immuables en groupe. Aucun document non applicable n'est construit. Les petites variations
sur les profils sans nouvelle annexe relèvent du bruit de mesure; les temps restent propres
à la machine et à ces profils.

## Prochains formulaires

Les autres annexes demandent de nouvelles entrées ou des règles fiscales supplémentaires.
Leur absence ne doit pas être confondue avec un calcul de ces situations à zéro.

| Document ou famille | Entrées à modéliser avant son calcul |
| --- | --- |
| `5005-S10`, `TP-1.D.R` | Travail autonome, emploi hors Québec, retenues réelles AE/RQAP; les formulaires excluent le cas du seul salarié québécois |
| `T2125`, `TP-80`, `TP-1.D.L` | Revenus et dépenses d'entreprise, amortissement et revenus nets autonomes |
| Annexe 7 fédérale | Cotisations REER datées, inutilisées, RAP/REEP et maximum déductible; `rrsp_deduction` est seulement un montant déjà déterminé |
| `T1032`, `TP-1.D.Q` | Conjoint, revenus admissibles et choix de fractionnement |
| Annexes C, D, H, J, T et V du Québec | Frais de garde, logement, personne aidée, services aux aînés, études, dons et conditions familiales propres à chaque crédit |
| Parties détaillées des annexes 3 et G | Dispositions par catégorie, prix de base, produits, dépenses, provisions et reports de pertes |

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
   fiscalité et en finances publiques. La refonte 0.3 a vérifié la numérotation sur le TP-776.42, mais conserve le calcul 0.2 :
   revenu imposable après plancher à zéro et cotisations bonifiées seules dans les déductions
   rajoutées. Les corrections fiscales sont distinctes de cette refonte sans changement de montants.

## Hors portée de la v0.1

Travail autonome, couple et fractionnement du revenu de pension, transferts entre conjoints,
enfants et crédits remboursables (solidarité, allocation famille), frais médicaux, dons,
acomptes provisionnels, pertes reportées, résidents d'une autre province.
