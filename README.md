# impotsqc

Calcul des déclarations de revenus **fédérale (T1)** et **du Québec (TP-1)**, ligne par ligne,
et de la **pension alimentaire pour enfants** selon le modèle québécois, pour un script ou un agent. On décrit un contribuable fictif et on obtient chaque ligne des
formulaires et annexes : montant, numéro de ligne officiel, libellé, et la règle appliquée.

> **Statut : 0.6.0 en préparation (alpha).** Le calcul exige maintenant une réponse explicite sur le conjoint
> fiscal et les mois exemptés de cotisation RAMQ. L'annexe K utilise le revenu familial, les
> enfants admissibles et les deux semestres. Les paramètres RAMQ 2026 restent provisoires.
> Voir les [limites de calcul](PLAN.md#assurance-medicaments-050).

## Portée

- Années : **2025 et 2026**, puis une année de plus chaque année. Les années publiées ne changent pas.
- Situations : **salarié** (emploi, cotisations RRQ/AE/RQAP, déduction REER, placements) et
  **retraité** (FERR et REER, RRQ, PSV et son remboursement, crédits d'âge, de pension, de
  personne vivant seule, de prolongation de carrière), dividendes et gains en capital.
- Revenus supplémentaires : rentes de RPA/REER, FERR de survivant, AE régulière/spéciale,
  RQAP, SRG reçu, aide sociale et indemnités de remplacement. Cotisations RPA et cotisations
  syndicales/professionnelles : déduction fédérale et crédit québécois distincts.
- Assurance médicaments : personne avec ou sans conjoint fiscal, revenu net du conjoint,
  enfants admissibles et mois exemptés confirmés. Chaque personne paie sa propre cotisation.
- Couples : `compute_couple` calcule les revenus nets des deux personnes, les réutilise pour
  la RAMQ et met en commun les droits d'âge/retraite/vivre seul de l'annexe B avant partage.
  Il applique aussi les montants fédéraux pour conjoint soutenu (annexe 5), les transferts de
  droits d'âge/pension (annexe 2 du Québec) et les crédits inutilisés québécois (ligne 431).
- Fractionnement : T1032 et annexe Q pour les rentes RPA/REER et FERR saisis, avec choix
  distincts, plafonds, prorata fédéral, crédits de pension et transfert obligatoire des retenues.
- Retenues et acomptes réellement fournis : calcul des soldes/remboursements, distincts de
  l'impôt annuel. Aucun paiement n'est estimé lorsque les renseignements sont absents.
- Hors portée pour l'instant : travail autonome, autres crédits/transferts familiaux,
  pensions particulières (conventions de retraite, vétérans, RPAC et pensions étrangères),
  crédits pour enfants, frais médicaux, dons et crédits remboursables non encore implémentés.
  Le calcul global d'un couple reste incomplet et porte un avertissement.

## Usage

```python
from impotsqc import Taxpayer, compute

r = compute(Taxpayer(year=2026, age=66, rrif_income=30_000, oas_pension=8_900,
                     has_spouse=False, drug_plan_exempt_months=(), drug_plan_dependent_children=0))
r.forms["T1"]["23600"].amount           # revenu net fédéral
r.forms["TP-1"]["275"].amount            # revenu net du Québec
r.forms["TP-1.D.B"]["34"].amount        # résultat de l'annexe B
r.forms["TP-1.D.B"].source              # URL du PDF officiel
r.forms["TP-1"]["361"].refs             # ("TP-1.D.B:34",)
r.forms["TP-1.D.B"]["22"].params        # paramètres d'âge consultés
r.total_payable                # impôts fédéral et du Québec, cotisations comprises
r.to_dict()                    # JSON, pour un agent
```

`r.federal` et `r.quebec` restent des alias de `r.forms["T1"]` et `r.forms["TP-1"]`.

Pour coordonner deux contribuables fictifs, sans ressaisir le revenu du conjoint :

```python
from impotsqc import CoupleOptions, Taxpayer, compute_couple, required_couple_questions

first = Taxpayer(year=2025, age=66, rrif_income=25_000, has_spouse=True,
                 drug_plan_exempt_months=tuple(range(1, 13)))
second = Taxpayer(year=2025, age=67, rrif_income=25_000, has_spouse=True,
                  drug_plan_exempt_months=tuple(range(1, 13)))
choices = CoupleOptions(spouse_amount_claimant="neither", federal_transfers=True)
required_couple_questions(first, second, options=choices)  # {} : admissibilité et couverture confirmées
couple = compute_couple(first, second, schedule_b_first_share=0.75, options=choices)
couple.first.forms["TP-1.D.B"]["34"].amount    # 9 951,65625 $, avant arrondi d'affichage
couple.second.forms["TP-1.D.B"]["34"].amount   # 3 317,21875 $
couple.refs["first/TP-1.D.B:12"]              # ("second/TP-1:275",)
couple.to_dict()                             # deux déclarations et liens interpersonnels
```

Le partage par défaut est de 50 % chacun; `schedule_b_first_share` permet de choisir de 0 à 1.
Ce choix n'est pas une optimisation. Les lignes 23 et 28 de B exposent les droits du conjoint;
33 indique la part demandée par l'autre personne. Les clés `1.C`, `8.C`, `9.C` désignent la
colonne « conjoint » de la grille de retraite; `1`, `8`, `9` restent la colonne du déclarant.
`lives_alone=True` confirme l'admissibilité fiscale annuelle, y compris la situation particulière
admissible de conjoints séparés involontairement; le statut conjugal reste une réponse distincte.

Les `Line.refs` restent locaux à chaque déclaration. `CoupleReturn.refs` ajoute les liens entre
personnes au format `first/CODE:ligne` et `second/CODE:ligne`, sans inventer de codes de formulaire.
Un revenu du conjoint déjà saisi est vérifié au cent, puis remplacé par le montant calculé non
arrondi. `CoupleOptions` exige de confirmer le demandeur du montant pour conjoint, son
admissibilité au supplément pour infirmité s'il demande ce montant et l'admissibilité aux
transferts fédéraux. `None` signifie inconnu : le calcul fournit les questions bloquantes.
Le statut québécois et le faible revenu ne remplacent pas ces confirmations.

Les parties conjoint de l'annexe 5 alimentent T1:30300 et 30425; l'annexe 2 propre au Québec
transfère les droits d'âge/pension inutilisés à T1:32600. Les études, le handicap et les autres
personnes à charge restent à ajouter. Les lignes 413 et 430 du TP-1 conservent les soldes
négatifs. Le transfert québécois est inscrit à 431, négatif chez le cédant et positif chez le
bénéficiaire, pour soustraire les crédits reçus à 432. `transfer_unused_quebec=False` permet
de ne pas le demander. La grille 8 du TP-776.42 recalcule la portion admise à l'IMR.
Les choix et le partage de B figurent dans `CoupleReturn.to_dict()`.
Les pensions particulières et les crédits restants sont signalés dans les avertissements du total.

Pour choisir un fractionnement, fournir deux choix indépendants dans `CoupleOptions`.
Exemple fictif avec FERR ordinaires, sans pension liée à un décès dans l'année :

```python
from impotsqc import CoupleOptions, PensionSplit, TaxPayments, Taxpayer, compute_couple

first = Taxpayer(year=2025, age=66, rrif_income=60_000, has_spouse=True,
    drug_plan_exempt_months=tuple(range(1, 13)),
    payments=TaxPayments(federal_withheld=10_000, quebec_withheld=12_000,
                         federal_instalments=0, quebec_instalments=0))
second = Taxpayer(year=2025, age=60, has_spouse=True,
    drug_plan_exempt_months=tuple(range(1, 13)), payments=TaxPayments(0, 0, 0, 0))
choices = CoupleOptions(spouse_amount_claimant="neither", federal_transfers=True,
    federal_pension_split=PensionSplit(donor="first", amount=30_000, eligible=True,
        tax_withheld=10_000, months_as_spouses=12, tax_year_months=12,
        same_year_survivor_pension=0),
    quebec_pension_split=PensionSplit(donor="first", amount=20_000, eligible=True,
        tax_withheld=12_000))
couple = compute_couple(first, second, options=choices)
couple.first.forms["T1032"]["22"].amount       # 30 000 $, reportés à T1:21000 et T1:11600
couple.first.forms["TP-1.D.Q"]["22"].amount   # 20 000 $, reportés à TP-1:245 et TP-1:123
couple.second.federal["31400"].amount          # 0 : FERR reçu par un bénéficiaire de moins de 65 ans
couple.second.quebec["451.3"].amount           # 4 000 $ de retenues québécoises reçues
couple.first.federal_balance                  # solde signé : négatif = remboursement
couple.first.quebec_balance
```

`required_couple_questions` demande les confirmations manquantes. `tax_withheld` est la part
réellement retenue sur les pensions admissibles; les feuillets mixtes doivent être ventilés.
Le fédéral demande les mois d'union et ceux de l'année fiscale du cédant. L'exception de la
note 1 pour un bénéficiaire de moins de 65 ans peut aussi demander la part des FERR/rentes
provenant d'un décès de conjoint survenu dans l'année (`same_year_survivor_pension`). Une
origine de survivant sans l'année du décès ne suffit pas à confirmer cette exception.

Le T1032 figure dans les deux déclarations, avec les mêmes montants et des liens adaptés à
chaque rôle. L'annexe Q figure uniquement chez le cédant. Les revenus nets, remboursements
AE/PSV, crédits d'âge/pension, B/F/K et l'IMR sont calculés après les transferts de revenus.
Les limites de 50 % sont vérifiées; aucun montant ni sens optimal n'est choisi automatiquement.
Un choix nul ne construit pas d'annexe. Le prorata au décès du T1032 est calculé, avec un
avertissement sur les autres règles des déclarations de décès encore à implémenter.

`TaxPayments` exige les quatre montants, y compris zéro : retenues fédérales et québécoises,
acomptes fédéraux et québécois. Les propriétés `federal_balance` et `quebec_balance` sont
`None` si ces données sont absentes; sinon elles sont ajoutées au résumé JSON. Les lignes
48400/48500 du T1 et 478/479 du TP-1 distinguent remboursement et solde dû, chacun en valeur
positive. Les soldes sont calculés avant intérêts, pénalités et tolérances de perception.
`total_payable` reste la charge fiscale annuelle, cotisations sociales comprises : saisir
les paiements ne modifie pas cette charge.

Les annexes sont présentes seulement lorsqu'elles s'appliquent dans la portée du moteur :

| Code | Document | Condition de présence |
| --- | --- | --- |
| `T1`, `TP-1` | Déclarations principales | Toujours |
| `5000-D1` | Feuille de travail fédérale | Pension admissible, suppléments fédéraux ou récupération AE/PSV; grilles 23500, 25000 et 31400 |
| `5000-S5` | Montants pour conjoint et personnes à charge | Avec `compute_couple`, montant positif pour conjoint soutenu ou aidant; sections 30300 et 30425 seulement |
| `5005-S2` | Montants fédéraux transférés du conjoint, version Québec | Avec `compute_couple`, admissibilité confirmée et droits d'âge/pension inutilisés positifs |
| `T1032` | Choix conjoint de fractionnement de pension | Choix fédéral positif et admissible, copie dans les deux déclarations |
| `TP-1.D.Q` | Revenus de retraite transférés au conjoint | Choix québécois positif, cédant de 65 ans ou plus; copie chez le cédant seulement |
| `5000-S3`, `TP-1.D.G` | Gains en capital | Gain net positif fourni; total et inclusion seulement |
| `5005-S8` | Cotisations au RRQ | Revenu d'emploi positif, 19 à 72 ans, hypothèse d'année complète |
| `TP-1.D.U` | Déduction RRQ du salarié | Cotisation bonifiée positive, 19 à 72 ans |
| `TP-1.D.B` | Allègements fiscaux | Âge admissible, personne vivant seule ou revenu de retraite; droits du conjoint inclus avec `compute_couple` |
| `TP-1.D.F` | Cotisation au FSS | Revenu assujetti au-dessus du premier seuil |
| `TP-1.D.K` | Assurance médicaments | Revenu familial au-dessus de l'exemption de base et au moins un mois non exempté |
| `TP-752.PC` | Prolongation de carrière | 65 ans et plus et revenu de travail positif |
| `T691` | IMR fédéral | Revenu imposable rajusté au-dessus de l'exemption |
| `TP-776.42`, `TP-1.D.E` | IMR du Québec et redressement | Revenu imposable modifié au-dessus de l'exemption |

La présence d'un formulaire ne signifie pas nécessairement un montant à payer ou un crédit positif.
Seules les parties utiles à la situation et couvertes par le moteur sont remplies. Pour le T691,
les clés distinguent les parties : `"P1-93"`, `"P5-11"`, `"P6-14"`; la partie 6 n'est remplie
que si l'impôt minimum dépasse l'impôt ordinaire. Pour l'annexe B, les lignes 1, 8 et 9 désignent
la grille de retraite. La dernière ligne de l'annexe K est `"98"` (cotisation personnelle : `"90"`).

Pour un salarié ayant réalisé un gain :

```python
r = compute(Taxpayer(year=2025, age=40, employment_income=80_000, capital_gains=20_000,
                     has_spouse=False, drug_plan_exempt_months=(), drug_plan_dependent_children=0))
r.forms["5000-S3"]["19900"].amount     # 10 000 $, repris au T1, ligne 12700
r.forms["TP-1.D.G"]["108"].amount      # 10 000 $, repris au TP-1, ligne 139
r.forms["5005-S8"]["P2-35"].amount     # crédit RRQ de base, repris au T1, ligne 30800
r.forms["5005-S8"]["P2-47"].amount     # déduction RRQ bonifiée, reprise au T1, ligne 22215
r.forms["TP-1.D.U"]["23"].amount       # même déduction, reprise au TP-1, ligne 248
```

Les annexes 3 et G commencent au gain net déjà fourni dans `capital_gains`. Elles ne ventilent
pas les transactions, leurs prix de base, les provisions ou les catégories de biens. L'annexe 8
utilise des clés `P1-A`, `P2-35`, etc., car la numérotation recommence à chaque partie. Les retenues
RRQ sont simulées égales aux cotisations requises; les trop-perçus et choix de cessation ne sont
pas calculés. À 18 ans ou dès 73 ans, les annexes 8 et U sont absentes et un avertissement signale
la limite du calcul annuel hérité : **les montants historiques ne sont pas corrigés** par cette
extraction. La ligne TP-1 `98.1` expose le salaire admissible simulé, plafonné au maximum supplémentaire.

Les annexes fédérale 10 et québécoise R concernent notamment le travail autonome ou l'emploi
hors Québec, situations encore hors portée. Elles ne sont pas ajoutées pour un salarié travaillant
uniquement au Québec. Les [prochaines extensions](PLAN.md#prochains-formulaires) précisent les
entrées manquantes.

Chaque `Form` porte `code`, `title`, `version`, `source` et `lines`. Chaque `Line` porte son
numéro, son libellé, son montant, sa règle, ses `refs` (`"CODE:ligne"`) et ses `params`
(`"fichier.table.clé"`). Par exemple, `quebec.schedule_b.age` renvoie à
`load_parameters(r.taxpayer.year)["quebec"]["schedule_b"]["age"]`; la même table contient
`source`, `ref` et `status` pour retrouver la publication officielle.

`r.to_dict()` contient `year`, `taxpayer`, `forms`, `summary` et `warnings`. Chaque entrée de
`forms` contient les métadonnées du document et un dictionnaire `lines`; chaque ligne contient
`label`, `amount`, `rule`, `refs` et `params`. Les montants sont arrondis au cent dans le JSON
seulement. Les clés historiques `federal` et `quebec` restent disponibles en 0.6
comme dictionnaires de lignes; leur retrait est différé. Les anciennes clés préfixées sont déplacées dans leurs annexes :
voir la [table de migration](CHANGELOG.md#030--2026-10-04).

La numérotation et les versions des formulaires fiscaux sont celles de 2025. Pour l'année 2026,
les métadonnées portent le statut `rule_2025`, avec les paramètres fiscaux de 2026; les PDF 2026
ne sont pas encore utilisés.

### Pensions, prestations et cotisations

Les entrées décrivent la situation fiscale; les numéros de formulaire restent dans les sorties.
Une rente de RPA est distincte d'un retrait REER ordinaire, lequel va à `TP-1:154` et n'ouvre
pas le montant pour revenus de retraite. `PensionIncome` couvre les rentes canadiennes et FERR;
les transferts directs et pensions étrangères ne sont pas inclus dans ce type.

```python
from impotsqc import Benefits, Deductions, PensionIncome, Taxpayer, compute

r = compute(Taxpayer(
    year=2025, age=55, has_spouse=False,
    drug_plan_exempt_months=tuple(range(1, 13)),  # assurance privée confirmée, profil fictif
    pensions=(PensionIncome(amount=20_000, kind="rpp"),),
    benefits=Benefits(ei_regular=5_000, ei_repayment_exempt=False),
    deductions=Deductions(rpp=1_000, union_dues_federal=575, union_dues_quebec=500),
))
r.forms["5000-D1"]["31400-8"].amount  # revenu admissible au montant pour pension
r.forms["T1"]["20700"].amount          # déduction RPA
r.forms["TP-1"]["397"].amount         # crédit québécois de cotisations syndicales
```

Pour `kind="rrif"` ou `"rrsp_annuity"` avant 65 ans, confirmer `from_deceased_spouse`.
Les prestations AE régulières, spéciales autres que parentales, de maternité/parentales et RQAP
se saisissent respectivement dans `ei_regular`, `ei_special`, `ei_maternity_parental` et `qpip`,
sans doublon. `ei_repayment_exempt` exige une réponse explicite dès qu'il y a de l'AE régulière.
Les remboursements de trop-perçus (`ei_repaid`, `qpip_repaid`, `oas_overpayment_recovered`) sont
les sommes déductibles dans l'année; le moteur calcule séparément la récupération selon le revenu.
Le choix d'imputer un remboursement à une année antérieure reste à ajouter.

L'aide sociale fédérale (`social_assistance`) et québécoise (`quebec_social_assistance`) peuvent
être attribuées différemment entre conjoints : le second montant doit être confirmé, même à zéro.
Pour les indemnités, fournir `quebec_replacement_adjustment` depuis la case M du relevé 5, ou
un TP-752.0.0.6 déjà rempli, sans déduire ce redressement du seul montant des indemnités.
Le SRG fourni dans `federal_supplements` est un montant **reçu**, pas une prestation prévisionnelle.

La suite de l'implémentation complète est suivie dans [IMPLEMENTATION.md](IMPLEMENTATION.md).

### Questions à poser avant le calcul

`compute` ne présume plus que la personne est sans conjoint et assujettie à la RAMQ toute
l'année. `required_questions` donne les questions encore nécessaires, indexées par les noms
des champs. Si elles restent sans réponse, `compute` lève `MissingInformationError` avant de
produire des formulaires ou un total. La librairie n'appelle jamais `input()`.

```python
from dataclasses import replace
from impotsqc import Taxpayer, compute, required_questions, MissingInformationError

tp = Taxpayer(year=2025, age=40, interest_income=25_000)
questions = required_questions(tp)       # questions en français, avec les sources officielles
try:
    compute(tp)
except MissingInformationError as error:
    payload = error.to_dict()           # {"error": "missing_information", "questions": {...}}

# Après avoir obtenu les réponses, ici pour un ménage fictif :
tp = replace(tp, has_spouse=True, spouse_net_income=12_000,
             drug_plan_exempt_months=(1, 2, 3), drug_plan_dependent_children=0)
r = compute(tp)
r.forms["TP-1.D.K"]["40"].amount       # revenu familial : 37 000 $
r.forms["TP-1.D.K"]["62"].amount       # 3 mois exemptés
r.quebec["447"].amount                 # cotisation personnelle : 140,301 $, sans arrondi interne
```

- `has_spouse=None` signifie inconnu; `False` confirme l'absence de conjoint fiscal au
  31 décembre. Ce statut suit les [définitions de Revenu Québec](https://www.revenuquebec.ca/fr/definitions/conjointe-ou-conjoint-au-31-decembre/),
  notamment les unions de fait, séparations et décès. Il ne se déduit jamais de `lives_alone`.
  Ce dernier décrit l'admissibilité au montant pour personne vivant seule de l'annexe B.
- Si `has_spouse=True`, `spouse_net_income` est requis, même lorsqu'il est nul. Fournir la
  **ligne 275 du TP-1** du conjoint, et non son salaire brut ou son revenu net fédéral.
- `drug_plan_exempt_months=None` signifie inconnu. `()` ou `[]` confirme zéro mois exempté;
  `tuple(range(1, 13))` confirme douze mois exemptés et rend la cotisation nulle. Les mois
  mixtes sont des entiers uniques de 1 à 12; une liste JSON est aussi acceptée.
- Les mois exemptés comprennent la couverture **privée de base**, personnelle ou par un
  conjoint/parent, et les autres exemptions confirmées selon le [guide de la ligne 447](https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/aide-par-ligne/400-a-447-impot-et-cotisations/ligne-447/).
  Une journée admissible exempte le mois. Une couverture complémentaire seule ne suffit pas.
  L'API ne détermine pas automatiquement les exemptions d'études, de SRG ou les autres cas
  particuliers : confirmer l'admissibilité avec le guide, y compris ses cas exigeant de
  communiquer avec Revenu Québec. Ne pas assimiler inscription à la RAMQ et obligation de cotiser.
- `drug_plan_dependent_children` exige de confirmer le nombre d'enfants admissibles selon
  l'annexe K, y compris zéro. Ce renseignement n'est pas demandé si les douze mois sont exemptés.

Pour les couples, l'annexe K calcule uniquement la prime personnelle avec le barème familial.
Le choix de payer celle du conjoint sur la même déclaration n'est pas modélisé. L'annexe B
utilise également le revenu familial, mais ne calcule que les montants personnels d'âge et de
retraite : les droits du conjoint et leur répartition restent hors portée, comme les autres
crédits et transferts entre conjoints. Ces limites sont présentes dans `r.warnings`.

### Pension alimentaire pour enfants

```python
from impotsqc import ChildSupportCase, ParentIncome, compute_child_support

cas = ChildSupportCase(year=2026, parent_a=ParentIncome(salary=90_000), parent_b=ParentIncome(salary=60_000),
                       custody_days_a=(100, 100), childcare=3_000)   # jours par année chez le parent A, par enfant
r = compute_child_support(cas)
r.section, r.payer, r.annual_amount    # section de la partie 5, parent débiteur, pension annuelle
r.form["401"].amount                   # contribution alimentaire parentale de base (table de l'année)
r.form.code, r.form.version             # "FIXATION-PA", "2016-01"
r.form.source                          # PDF officiel du formulaire de fixation
```

Le module suit le Formulaire de fixation des pensions alimentaires pour enfants du Québec,
ligne par ligne, avec la table de fixation et la déduction de base de chaque année. Il choisit
automatiquement la section du temps de garde : garde exclusive (20 % et moins), droit de visite
et de sortie prolongé (20 % à 40 %), garde exclusive attribuée à chacun des parents, garde
partagée (au moins 40 % chacun) ou combinaison. Il applique aussi la capacité de payer (50 % du
revenu disponible). `ParentIncome.from_tax_return(...)` reprend les revenus d'une déclaration
calculée par `compute`. Les ajustements motivés, les ententes et les difficultés excessives
relèvent du tribunal et ne sont pas calculés.

L'API est en anglais et la documentation en français, comme dans `retraiteqc`. Les libellés des
lignes reprennent ceux des formulaires officiels.

## Structure

```
src/impotsqc/              le code (AGPL)
src/impotsqc/parametres/   un dossier par année : paramètres en TOML, chacun avec sa source officielle
oracle/AAAA/               relevés d'un oracle externe (local, ignoré par git; tests sautés en son absence)
tests/
benchmarks/compute.py      mesure de compute() avec timeit, cinq profils fictifs
```

Les formules sont communes à toutes les années. Ce qui change d'une année à l'autre (taux,
seuils, montants, plafonds) vit dans les TOML de l'année. Les métadonnées des documents sont dans `formulaires.toml`. Voir [PLAN.md](PLAN.md#années).

## Sources

Les paramètres viennent **uniquement** de publications officielles : Agence du revenu du Canada,
Revenu Québec, Retraite Québec, RAMQ, ministère des Finances du Québec et de Canada. Chaque
valeur cite son document. Un calculateur externe sert d'**oracle de validation** : on compare les
résultats ligne par ligne pour des contribuables fictifs. Ses relevés restent hors du dépôt, et
chaque écart est tranché par un document officiel.

## Licence

[GNU AGPL 3.0 ou ultérieure](LICENSE). Aucun conseil fiscal : les résultats n'engagent ni l'ARC
ni Revenu Québec.
