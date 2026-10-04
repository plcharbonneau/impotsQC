# impotsqc

Calcul des déclarations de revenus **fédérale (T1)** et **du Québec (TP-1)**, ligne par ligne,
et de la **pension alimentaire pour enfants** selon le modèle québécois, pour un script ou un agent. On décrit un contribuable fictif et on obtient chaque ligne des
formulaires et annexes : montant, numéro de ligne officiel, libellé, et la règle appliquée.

> **Statut : 0.4.0 (alpha).** Les annexes 3 et 8 fédérales, G et U du Québec complètent les
> documents accessibles par `r.forms`. Aucun montant existant de 0.3.0 ne change. Les règles
> fiscales et leurs limites sont conservées; voir [PLAN.md](PLAN.md#points-dinterprétation).

## Portée

- Années : **2025 et 2026**, puis une année de plus chaque année. Les années publiées ne changent pas.
- Situations : **salarié** (emploi, cotisations RRQ/AE/RQAP, déduction REER, placements) et
  **retraité** (FERR et REER, RRQ, PSV et son remboursement, crédits d'âge, de pension, de
  personne vivant seule, de prolongation de carrière), dividendes et gains en capital.
- Hors portée pour l'instant : travail autonome, couple et transferts entre conjoints, enfants,
  frais médicaux, dons, crédits remboursables, acomptes provisionnels.

## Usage

```python
from impotsqc import Taxpayer, compute

r = compute(Taxpayer(year=2026, age=66, rrif_income=30_000, oas_pension=8_900))
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
Les annexes sont présentes seulement lorsqu'elles s'appliquent dans la portée du moteur :

| Code | Document | Condition de présence |
| --- | --- | --- |
| `T1`, `TP-1` | Déclarations principales | Toujours |
| `5000-S3`, `TP-1.D.G` | Gains en capital | Gain net positif fourni; total et inclusion seulement |
| `5005-S8` | Cotisations au RRQ | Revenu d'emploi positif, 19 à 72 ans, hypothèse d'année complète |
| `TP-1.D.U` | Déduction RRQ du salarié | Cotisation bonifiée positive, 19 à 72 ans |
| `TP-1.D.B` | Allègements fiscaux | Âge admissible, personne vivant seule ou revenu de retraite |
| `TP-1.D.F` | Cotisation au FSS | Revenu assujetti au-dessus du premier seuil |
| `TP-1.D.K` | Assurance médicaments | Revenu net au-dessus de l'exemption, assurance publique annuelle présumée |
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
r = compute(Taxpayer(year=2025, age=40, employment_income=80_000, capital_gains=20_000))
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
seulement. Les clés historiques `federal` et `quebec` restent disponibles en 0.4
comme dictionnaires de lignes; leur retrait est différé. Les anciennes clés préfixées sont déplacées dans leurs annexes :
voir la [table de migration](CHANGELOG.md#030--2026-10-04).

La numérotation et les versions des formulaires fiscaux sont celles de 2025. Pour l'année 2026,
les métadonnées portent le statut `rule_2025`, avec les paramètres fiscaux de 2026; les PDF 2026
ne sont pas encore utilisés.

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
