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
conteneurs JSON `federal` et `quebec` restent conservés en 0.5; leur retrait est différé.

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

## Assurance médicaments (0.5.0)

Correction fiscale demandée après l'extraction des annexes. Les renseignements absents ne
produisent plus de prime RAMQ présumée. `required_questions(Taxpayer)` rend un dictionnaire
champ → question; `compute` le reprend dans `MissingInformationError` et bloque le calcul tant
que des réponses sont nécessaires. Les questions n'exécutent aucune interaction et sont
sérialisables en JSON. Les années absentes restent refusées par le chargeur de paramètres.

Entrées : conjoint fiscal au 31 décembre (`has_spouse`, distinct de `lives_alone`), revenu net
québécois du conjoint lorsqu'il existe (`spouse_net_income`), mois exemptés de 1 à 12
(`drug_plan_exempt_months`) et nombre d'enfants admissibles (`drug_plan_dependent_children`).
`None` signifie inconnu; zéro, `False` et le tuple vide sont des réponses explicites. Le nombre
d'enfants n'est pas nécessaire si les douze mois sont exemptés. La couverture privée est celle
du régime de base; les exemptions spéciales sont déterminées par l'appelant à partir du guide.

L'[annexe K 2025](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.K%282025-12%29.pdf)
utilise les revenus nets du ménage et les exemptions familiales (36 à 48), les mois exemptés
par semestre (60 à 62), la grille avec ou sans conjoint, puis deux plafonds proratisés (84 à 90).
La ligne 98 reporte uniquement la cotisation personnelle; payer celle du conjoint relève d'un
choix non modélisé. Le régime privé couvrant toute l'année évite même de construire l'annexe.
Les taux et montants sont dans les TOML annuels. Les nouveaux paramètres 2026 restent des
estimations sourcées et signalées, en attendant l'annexe K 2026; aucune valeur préexistante n’est modifiée.

Le revenu du conjoint entre aussi dans l'annexe B, ligne 12, et dans sa réduction selon le
revenu familial. **Le calcul global du couple reste incomplet** : B ne met pas en commun les
droits d'âge/retraite du conjoint et n'en répartit pas le résultat; les autres crédits/transferts
entre conjoints et le fractionnement ne sont pas calculés. `warnings` indique ces limites.

Validation : 362 tests réussis avec les relevés locaux, incluant 49 nouveaux cas; 260 réussis
et 22 sautés dans une copie sans oracle. Les tests
historiques donnent explicitement les réponses qui étaient auparavant supposées. Ils conservent
leurs valeurs attendues; 500 profils supplémentaires gardent exactement leurs 92 540 montants
préexistants et leurs totaux. Les tests couvrent les 49 combinaisons de comptes de mois par
semestre pour chaque barème et année, les enfants, les seuils, la continuité, les questions,
les entrées invalides, les références et le JSON.

Mesure avec `timeit`, Python 3.14.3, mêmes cinq profils qu'en 0.4, paramètres chauds, entrées
préconstruites, médiane de sept répétitions de 10 000 appels, sans sérialisation :

| Profil | `main` 0.3.0 (µs) | Avant RAMQ 0.4.0 (µs) | Après 0.5.0 (µs) | RAMQ : après/avant |
| --- | ---: | ---: | ---: | ---: |
| Salarié | 23,531 | 35,410 | 36,466 | 1,030× |
| Retraité | 31,212 | 30,855 | 31,962 | 1,036× |
| Prolongation de carrière | 30,542 | 42,530 | 43,464 | 1,022× |
| IMR / gain en capital | 38,326 | 40,615 | 41,894 | 1,031× |
| Sans revenu | 19,729 | 19,328 | 19,762 | 1,022× |

Surcoût maximal de la correction RAMQ : **1,036×**. Depuis `main`, les quatre nouvelles
annexes et cette correction totalisent **1,55×** pour le salarié (légèrement au-dessus de la
cible indicative de 1,5×); les autres profils sont à 1,42× ou moins. Les mesures varient selon
la machine et sa charge. Le calcul conserve `Form.add` et les références explicites.

Aucune clé de formulaire ou de ligne n'est renommée; les changements d'entrée sont décrits
dans le `CHANGELOG` 0.5.0. Les nouveaux cas de couverture ou de ménage **changent les résultats**;
les hypothèses historiques, lorsqu'elles sont confirmées, reproduisent les montants historiques.

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

Les divergences historiques sont conservées dans les relevés locaux; une correction du moteur
ne modifie pas ces relevés et doit supprimer sa tolérance dans les tests.

1. **Retraits REER ordinaires : corrigé en 0.6.** Ils appartiennent à la ligne 154, point 6,
   et sont exclus du montant pour revenus de retraite. La ligne 122 accueille notamment les
   rentes de REER échu et les paiements FERR. L'ancienne interprétation incluait à tort les
   retraits ordinaires dans B. Les trois écarts historiques par année sont désormais résolus.
   Source officielle et migration : `CHANGELOG.md`, version 0.6.
2. **Maximum de la cotisation au régime d'assurance médicaments 2026 (annexe K).** Le maximum de
   l'année est la somme de six mois à chacun des deux tarifs mensuels, arrondie au dollar. C'est
   la règle de l'annexe K 2025 : 6 × 62,00 + 6 × 63,83 = 754,98 $, imprimé 755 $. Avec la prime
   de 789 $ annoncée par la RAMQ le 2026-06-30, cela donne 777 $ pour 2026. Valeur provisoire
   jusqu'à l'annexe K 2026. En 2025, l'oracle et impotsqc donnent tous deux 755 $.
3. **Impôt minimum : bases corrigées en 0.6.** Les deux régimes conservent le revenu imposable
   signé avant leurs rajouts. Le Québec rajoute aussi 50 % de la déduction pour travailleur
   (TP-776.42, ligne 157.9); le fédéral rajoute la part visée des cotisations syndicales
   (T691, ligne 51). Le report sur sept ans et les interactions avec les déductions/crédits
   encore absents du moteur restent à implémenter.

## Hors portée de la v0.1

La RAMQ des couples et les exemptions pour enfants sont couvertes depuis 0.5. Restent hors portée :
travail autonome, calcul fiscal complet du couple, fractionnement du revenu de pension, transferts
entre conjoints, crédits pour enfants et crédits remboursables (solidarité, allocation famille), frais médicaux, dons,
acomptes provisionnels, pertes reportées, résidents d'une autre province.


## Extension des revenus et déductions (0.6 en cours)

Première étape du registre [IMPLEMENTATION.md](IMPLEMENTATION.md) : pensions admissibles,
AE/RQAP et récupérations coordonnées avec la PSV, suppléments fédéraux reçus, aide sociale,
indemnités et redressement québécois fourni, cotisations RPA et syndicales/professionnelles.
Les différences fédéral/Québec sont conservées dans les entrées et dans les lignes officielles.
Les grilles 23500, 25000 et 31400 sont lisibles dans `forms["5000-D1"]` avec leurs dépendances.
Aucun objet annexe n'est créé pour une situation absente.

L'attribution familiale de l'aide sociale reste fournie explicitement; le calcul coordonné du
ménage viendra avec Q01/Q02. Le TP-752.0.0.6 n'est pas rempli par le moteur : le redressement
qui en résulte peut être saisi. La déduction des trop-perçus vise l'année courante; le choix
rétroactif et les crédits pour ces remboursements demeurent à compléter.


Validation de cette étape : **437 tests réussis**, dont validation locale, résolutions des refs,
absence de cycles, JSON, continuité et revenu disponible croissant. Copie sans oracle :
**335 réussis, 22 sautés**. Comparaison des TOML avec `main` : aucune valeur numérique
préexistante modifiée. Les tests historiques REER vérifient maintenant la concordance sans
l'exception qui masquait l'ancienne erreur; leurs relevés sont inchangés.

Mesure appariée de la version 0.5 (`main` 226de1f) et du code 0.6 en préparation, même Python
3.14.3, paramètres chauds, médiane de sept séries de 10 000 appels de `benchmarks/compute.py` :

| Profil | Avant 0.5 (µs) | Après cette étape (µs) | Rapport |
| --- | ---: | ---: | ---: |
| salarie | 36.512 | 37.596 | 1.030× |
| retraite | 31.974 | 34.936 | 1.093× |
| carriere | 43.610 | 45.002 | 1.032× |
| gain_capital | 42.051 | 43.695 | 1.039× |
| sans_revenu | 19.788 | 20.766 | 1.049× |

Le profil salarié est à 1,60× la référence historique 0.3 (23,531 µs), légèrement au-dessus
de la cible approximative de 1,5×. Cette cible et le mode rapide A03 restent ouverts dans le
registre; la faible variation par rapport à 0.5 ne vaut pas validation de la contrainte globale.


## Coordination des conjoints : annexe B (0.6.0 en préparation)

`compute_couple` remplit les revenus des deux personnes avant les crédits québécois. Les deux
phases du TP-1 sont communes à `compute` et `compute_couple`; il n'y a ni formule fiscale copiée
pour les couples ni calcul préalable de déclarations jetables. Le revenu du conjoint provient
de son TP-1:275 et remplace la saisie manuelle après vérification d'une éventuelle valeur fournie.

L'annexe B réunit les montants d'âge, de retraite et de personne vivant seule admissibles des
deux contribuables. La réduction familiale s'applique au total avant sa répartition. La même
ligne 32 figure dans les deux annexes; leurs lignes 34 totalisent ce montant. Le choix par défaut
est un partage égal, modifiable par `schedule_b_first_share`, sans optimisation automatique.
Sources : [annexe B 2025](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.B%282025-12%29.pdf)
et [guide, ligne 361](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/350-a-398-1-credits-dimpot-non-remboursables/ligne-361/).

`CoupleReturn.refs` porte les dépendances d'une personne vers l'autre. Elles sont séparées des
références locales de `Line`, ce qui préserve les codes officiels et le contrat de `TaxReturn`.
Les montants d'allocation sont calculés à partir du droit commun et du choix, sans lien réciproque
cyclique. Les liens d'entrée vers les revenus du conjoint se résolvent dans les deux déclarations.

Cette étape couvre Q02 en partie et les droits/partages de Q03. Le lot suivant ajoute les
parties conjoint des annexes 2/5 et TP-1:431; l'annexe A, le supplément monoparental et le
fractionnement restent dans le registre. Le total des couples porte un avertissement d'incomplétude.

Validation : 469 tests réussis, dont 31 nouveaux cas de couples; sans données locales ignorées,
367 réussis et 22 sautés. Montants 2025 indépendants, conservation du montant
familial, symétrie, questions, revenus incohérents, métadonnées, graphe acyclique et JSON.
Comparaison exacte à 91050c9 : 600 contribuables fictifs, 128 124 montants et tous les totaux
historiques de `compute` inchangés. Aucun paramètre ni montant attendu historique modifié.

Python 3.14.3, `timeit`, paramètres chauds, entrées préconstruites, médiane de 7 × 10 000 appels,
benchmark individuel avant/après cette étape (avant : 91050c9) :

| Profil | Avant (µs) | Après (µs) | Rapport |
| --- | ---: | ---: | ---: |
| Salarié | 36,833 | 37,918 | 1,029× |
| Retraité | 34,348 | 34,494 | 1,004× |
| Prolongation de carrière | 44,123 | 44,987 | 1,020× |
| Gain en capital | 42,756 | 43,576 | 1,019× |
| Sans revenu | 20,498 | 20,767 | 1,013× |

La référence 0.3 reste 23,531 µs pour le salarié : environ 1,61× à ce stade. L'objectif historique
de coût approximatif de 1,5× reste ouvert dans A03; ce tableau ne remplace pas cette référence.

Le couple retraité de l’exemple README (deux FERR de 25 000 $, 66 et 67 ans, couverture privée
annuelle) prend 95,456 µs pour les deux déclarations coordonnées, selon le même protocole.


## Crédits et transferts entre conjoints (0.6.0 en préparation)

Le T1 et le TP-1 séparent maintenant revenus, droits personnels et impôt final, dans les mêmes
objets Form. Le calcul du montant pour conjoint et des crédits transférables consulte les
revenus définitifs et les droits personnels du partenaire avant de compléter les deux impôts.
Aucun formulaire complet n'est calculé puis jeté.

- `CoupleOptions` demande une confirmation du soutien/admissibilité du conjoint et des
  conditions fédérales; le statut québécois au 31 décembre ne les implique pas.
- `5000-S5` : sections 30300 et 30425; `5005-S2` : montants inutilisés d'âge/pension vers
  32600. Les droits de handicap et d'études compléteront S2 avec leurs propres modules.
- TP-1:413 et 430 conservent les valeurs négatives prescrites. Le bénéficiaire déduit à 432
  la valeur absolue reçue à 431; le cédant reprend son solde négatif à 431. Le choix
  `transfer_unused_quebec=False` désactive ce transfert.
- La grille 8 du TP-776.42 recalcule le crédit transférable admis à l'IMR depuis les crédits
  et l'impôt du conjoint : il peut différer de la moitié de 431 en présence de dividendes.
  Les attributions B.1/B.2 d'études et de dons restent à ajouter avec ces entrées.
- Les liens interpersonnels sont dans `CoupleReturn.refs`; ses choix et le partage sont
  sérialisés. Aucun crédit de conjoint n'est construit dans `compute` individuel.

Sources : [annexe 2 du Québec](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s2/5005-s2-25f.pdf),
[annexe 5](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5000-s5/5000-s5-25f.pdf),
[TD1 2026](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/td1/td1-26f.pdf),
[TP-1 2025](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D%282025-12%29.pdf),
[guide de la ligne 431](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/400-a-447-impot-et-cotisations/ligne-431/),
[TP-776.42, grilles 7/8](https://www.revenuquebec.ca/documents/fr/formulaires/tp/TP-776.42%282025-10%29.pdf).

Validation : 497 tests, dont 28 nouveaux cas de transferts; copie sans données locales :
395 réussis et 22 sautés. Cas 2025/2026, infirmité, extinction, pension avant 65 ans,
IMR/dividendes, non-double-comptage, symétrie, questions, références acycliques et JSON.
600 profils comparés à adb1d3c : tous les totaux inchangés; sur 128 124 montants, huit soldes
413/430 deviennent négatifs conformément au TP-1. Les 202 entrées numériques préexistantes
des TOML sont identiques.


Mesure appariée de ce lot (avant : adb1d3c; après nettoyage des références du chemin
individuel), Python 3.14.3, médiane de 7 × 10 000 appels, entrées préconstruites, paramètres
chauds et sans JSON :

| Profil | Avant (µs) | Après (µs) | Rapport |
| --- | ---: | ---: | ---: |
| Salarié | 37,496 | 39,496 | 1,053× |
| Retraité | 34,567 | 37,133 | 1,074× |
| Prolongation de carrière | 44,635 | 48,755 | 1,092× |
| Gain en capital | 43,222 | 47,183 | 1,092× |
| Sans revenu | 20,807 | 22,233 | 1,069× |

La première mesure avant nettoyage était de 42,042 µs pour le salarié; les références des
crédits individuels ne sont plus reconstruites ni cherchées parmi des lignes encore absentes.
Le calcul individuel ne construit ni options de couple ni annexes 2/5. Le salarié reste à
1,68× la référence historique 0.3 (23,531 µs); A03 et la cible approximative de 1,5× demeurent
ouverts, sans déplacement de la référence historique.

Le calcul coordonné de deux FERR de 25 000 $ (66 et 67 ans, 2025, assurance privée annuelle,
partage égal de B, transferts fédéraux confirmés) prend 111,817 µs pour les deux déclarations,
selon le même protocole. Le lot précédent, qui ne calculait pas ces transferts, prenait 95,456 µs.


## Fractionnement et retenues de pension (0.6.0 en préparation, 2026-10-05)

Les choix fédéral et québécois sont deux données `PensionSplit` distinctes. Un seul cédant
est choisi par régime; aucune recherche automatique d'un partage optimal n'est effectuée.
La ventilation des pensions RPA/FERR/rentes REER est commune au T1 et au T1032. Les documents
sont calculés avant les revenus nets, ce qui évite de reconstruire les déclarations après
le fractionnement. Les références du T1032 suivent les sources de chaque personne : locales
dans `Line.refs`, vers l'autre déclaration dans `CoupleReturn.refs`.

Le T1032 conserve les pensions initiales à 68020, le prorata de mois à 18, le plafond à 21,
le choix à 22, puis les droits de crédit à 31/34 et les retenues à 68050/39/42. La note 1
est appliquée au bénéficiaire de moins de 65 ans; un décès survenu dans l'année est confirmé
séparément de la seule origine de survivant. L'annexe Q, réservée au cédant de 65 ans ou plus,
reprend le choix à 22 et l'impôt transféré à 58. Le régime québécois ne reprend pas le prorata
fédéral de l'état civil.

Les déductions 21000/245 et revenus 11600/123 précèdent les récupérations AE/PSV, les crédits
et l'IMR. Les grilles de retraite B reprennent 122 + 123 − 245; F déduit 245 à 46. Les montants
peuvent différer entre régimes, car les deux personnes de cette API résident au Québec.

`TaxPayments` exige les retenues et acomptes réels des deux régimes. Les calculs de solde
reprennent les crédits déjà calculés; ils ne modifient pas la charge fiscale annuelle. Les
soldes restent inconnus sans cet objet. Les reports d'impôt, trop-perçus de cotisations,
transferts interprovinciaux et de remboursement restent dans leurs étapes du registre.

Sources : [T1032 2025](https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t1032/t1032-25f.pdf),
[annexe Q](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.Q%282025-12%29.pdf),
[guide, lignes 122/123](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.G%282025-12%29.pdf),
[annexe B](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.B%282025-12%29.pdf),
[annexe F](https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.F%282025-12%29.pdf).

Validation : 546 tests, dont 49 nouveaux; copie publique : 444 réussis et 22 sautés. Montants
chiffrés 2025/2026, choix indépendants, prorata et plafonds, crédits avant 65 ans, note 1,
récupérations AE/PSV, bases IMR, symétrie, retenues, soldes, références et JSON. Comparaison
exacte de 600 profils et 128 124 montants avec 9811dc2; tous les totaux sont identiques.
Les 1 698 valeurs numériques préexistantes des TOML (tables de pension alimentaire comprises) sont inchangées.

Q04 reste à compléter pour les conventions de retraite, les prestations admissibles de
vétérans, RPAC, pensions étrangères et exclusions pour transferts directs. Les formulaires
actuels exposent seulement les pensions explicitement représentées par les entrées. Un
avertissement distingue le prorata T1032 au décès des autres règles de décès encore absentes.


Mesure du lot fractionnement, Python 3.14.3, mêmes cinq entrées préconstruites, paramètres
chauds, médiane de 7 × 10 000 appels avec `timeit` (`benchmarks/compute.py`). Avant : 9811dc2.

| Profil individuel | Avant (µs) | Après (µs) | Rapport |
| --- | ---: | ---: | ---: |
| Salarié | 39,951 | 39,857 | 0,998× |
| Retraité | 37,217 | 39,421 | 1,059× |
| Prolongation de carrière | 49,867 | 49,786 | 0,998× |
| Gain en capital | 48,543 | 48,438 | 0,998× |
| Sans revenu | 22,443 | 22,607 | 1,007× |

Un couple fictif de 66/67 ans en 2025, FERR de 60 000/10 000 $, avec transferts fédéral de
30 000 $ et québécois de 20 000 $, retenues/acompte nuls confirmés, assurance privée annuelle,
12 mois d'union et transferts fédéraux de crédits confirmés, prend 146,704 µs pour les deux
déclarations. Ce profil diffère du couple de 25 000/25 000 $ mesuré au lot précédent.

Le salarié reste à 1,694× la référence historique 0.3 de 23,531 µs. La cible globale d'environ
1,5× n'est donc pas encore atteinte; A03 conserve le travail de performance. Les deux nouveaux
formulaires ne sont construits que pour un choix de fractionnement positif.
