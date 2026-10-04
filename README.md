# impotsqc

Calcul des déclarations de revenus **fédérale (T1)** et **du Québec (TP-1)**, ligne par ligne,
et de la **pension alimentaire pour enfants** selon le modèle québécois, pour un script ou un agent. On décrit un contribuable fictif et on obtient chaque ligne des
formulaires et annexes : montant, numéro de ligne officiel, libellé, et la règle appliquée.

> **Statut : 0.2.0 (alpha).** Le T1 et le TP-1 2025 et 2026 se calculent ligne par ligne, impôt
> minimum de remplacement et crédit pour prolongation de carrière compris. Ils concordent avec un
> calculateur externe sur 38 cas fictifs par année, à deux points d'interprétation près (voir
> [PLAN.md](PLAN.md#points-dinterprétation)).

## Portée de la version 0.1

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
r.federal["23600"].amount      # revenu net (T1, ligne 23600)
r.quebec["275"].amount         # revenu net (TP-1, ligne 275)
r.total_payable                # impôts fédéral et du Québec, cotisations comprises
r.to_dict()                    # JSON, pour un agent
```

### Pension alimentaire pour enfants

```python
from impotsqc import ChildSupportCase, ParentIncome, compute_child_support

cas = ChildSupportCase(year=2026, parent_a=ParentIncome(salary=90_000), parent_b=ParentIncome(salary=60_000),
                       custody_days_a=(100, 100), childcare=3_000)   # jours par année chez le parent A, par enfant
r = compute_child_support(cas)
r.section, r.payer, r.annual_amount    # section de la partie 5, parent débiteur, pension annuelle
r.form["401"].amount                   # contribution alimentaire parentale de base (table de l'année)
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
```

Les formules sont communes à toutes les années. Ce qui change d'une année à l'autre (taux,
seuils, montants, plafonds) vit dans les TOML de l'année. Voir [PLAN.md](PLAN.md#années).

## Sources

Les paramètres viennent **uniquement** de publications officielles : Agence du revenu du Canada,
Revenu Québec, Retraite Québec, RAMQ, ministère des Finances du Québec et de Canada. Chaque
valeur cite son document. Un calculateur externe sert d'**oracle de validation** : on compare les
résultats ligne par ligne pour des contribuables fictifs. Ses relevés restent hors du dépôt, et
chaque écart est tranché par un document officiel.

## Licence

[GNU AGPL 3.0 ou ultérieure](LICENSE). Aucun conseil fiscal : les résultats n'engagent ni l'ARC
ni Revenu Québec.
