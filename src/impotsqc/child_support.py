# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Modèle québécois de fixation des pensions alimentaires pour enfants, ligne par ligne.

Suit le Formulaire de fixation des pensions alimentaires pour enfants (annexe I du Règlement sur la
fixation des pensions alimentaires pour enfants, RLRQ, c. C-25.01, r. 0.4) :
- partie 2 : revenus annuels de chaque parent (lignes 200 à 209);
- partie 3 : revenu disponible (300 à 307);
- partie 4 : contribution alimentaire de base et frais (400 à 407);
- partie 5 : pension selon le temps de garde (sections 1, 1.1, 2, 3 ou 4);
- partie 6 : capacité de payer du débiteur (600 à 603).

Les deux colonnes du formulaire (« père », « mère ») sont appelées A et B : les lignes à deux
colonnes portent le suffixe `.A` ou `.B` (p. ex. `"305.A"`). Les ajustements motivés (lignes 512.1,
518.1, 526.1, 534.1, 564.1), l'entente entre les parents (partie 7) et les difficultés excessives
relèvent du tribunal et ne sont pas calculés. Montants annuels, sans arrondi intermédiaire.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .model import Form
from .parameters import load_parameters

DAYS = 365
EXCLUSIVE_MAX = 0.20   # droit de visite et de sortie de 20 % et moins : garde exclusive
SHARED_MIN = 0.40      # au moins 40 % du temps de garde chacun : garde partagée


@dataclass(frozen=True)
class ParentIncome:
    """Revenus annuels d'un parent (partie 2 du formulaire) et cotisations déductibles (302, 303).

    `investment_income` : intérêts et montant IMPOSABLE des dividendes (ligne 206). `other_income` :
    autres revenus (ligne 208), sans les transferts gouvernementaux liés à la famille, l'aide de
    dernier recours ni l'aide financière aux études.
    """

    salary: float = 0.0
    commissions: float = 0.0
    business_income: float = 0.0
    ei_qpip_benefits: float = 0.0
    support_received: float = 0.0
    pension_benefits: float = 0.0
    investment_income: float = 0.0
    net_rental_income: float = 0.0
    other_income: float = 0.0
    union_dues: float = 0.0
    professional_dues: float = 0.0

    @classmethod
    def from_tax_return(cls, tax_return, *, union_dues: float = 0.0, professional_dues: float = 0.0) -> "ParentIncome":
        """Revenus tirés d'une déclaration `impotsqc` (TP-1) : emploi (101) → 200; PSV, RRQ, pensions,
        REER et FERR (114, 119, 122) → 205; dividendes imposables et intérêts (128, 130) → 206; gains
        en capital imposables (139) → 208."""
        q = tax_return.quebec
        return cls(salary=q.amount("101"),
                   pension_benefits=q.amount("114") + q.amount("119") + q.amount("122"),
                   investment_income=q.amount("128") + q.amount("130"),
                   other_income=q.amount("139"),
                   union_dues=union_dues, professional_dues=professional_dues)

    def __post_init__(self) -> None:
        """Les cotisations déductibles ne peuvent pas être négatives."""
        if self.union_dues < 0 or self.professional_dues < 0:
            raise ValueError("cotisations syndicales et professionnelles : montants positifs attendus")


@dataclass(frozen=True)
class ChildSupportCase:
    """Situation à calculer.

    `custody_days_a` : pour chaque enfant commun, le nombre de jours par année passés avec le
    parent A (0 à 365; le reste avec le parent B). Frais annuels nets (lignes 403 à 405), présumés
    payés par le parent qui reçoit la pension (note 2 du formulaire).
    """

    year: int
    parent_a: ParentIncome
    parent_b: ParentIncome
    custody_days_a: tuple[float, ...]
    childcare: float = 0.0
    post_secondary: float = 0.0
    special_expenses: float = 0.0

    def __post_init__(self) -> None:
        """Au moins un enfant; jours entre 0 et 365; frais positifs."""
        if not self.custody_days_a:
            raise ValueError("au moins un enfant est requis")
        if any(not 0 <= d <= DAYS for d in self.custody_days_a):
            raise ValueError("jours de garde hors de [0, 365]")
        if min(self.childcare, self.post_secondary, self.special_expenses) < 0:
            raise ValueError("frais négatifs")


@dataclass(frozen=True)
class ChildSupportResult:
    """Formulaire rempli, section de la partie 5 utilisée, parent débiteur, pension annuelle et
    mensuelle (après la partie 6), avertissements."""

    case: ChildSupportCase
    form: Form
    section: str
    payer: str | None
    annual_amount: float
    warnings: tuple[str, ...] = field(default=())

    @property
    def monthly_amount(self) -> float:
        """Pension mensuelle (annuelle / 12)."""
        return self.annual_amount / 12

    def to_dict(self) -> dict:
        """Résultat en JSON simple, pour un script ou un agent."""
        return {"year": self.case.year, "case": asdict(self.case), "section": self.section, "payer": self.payer,
                "annual_amount": round(self.annual_amount, 2), "monthly_amount": round(self.monthly_amount, 2),
                "form": self.form.to_dict(), "warnings": list(self.warnings)}


def base_contribution(disposable_income: float, children: int, table: dict) -> tuple[float, bool]:
    """Ligne 401 : contribution de base selon la table. Rend (montant, au-delà de 200 000 $)."""
    if disposable_income <= 0:
        return 0.0, False
    columns = [table[k] for k in sorted(t for t in table if t.startswith("amounts_"))]
    bounds = table["upper_bounds"]

    def amount_for(k: int) -> float:
        """Montant pour k enfants (1 à 6) à ce revenu, excédent au-delà du plafond compris."""
        col = columns[k - 1]
        for upper, value in zip(bounds, col):
            if disposable_income <= upper:
                return float(value)
        excess = disposable_income - table["excess_over"]
        return col[-1] + table["excess_rates_by_children"][k - 1] * excess

    above = disposable_income > table["excess_over"]
    if children <= 6:
        return amount_for(children), above
    six, five = amount_for(6), amount_for(5)
    return six + (children - 6) * (six - five), above


def _classify(days_a: tuple[int, ...]) -> list[tuple[str, str, float]]:
    """Pour chaque enfant : (type, parent gardien ou « - », part de temps du parent non gardien ou
    de A en garde partagée). Types : exclusive, extended, shared."""
    out = []
    for d in days_a:
        share_a = d / DAYS
        if SHARED_MIN <= share_a <= 1 - SHARED_MIN:
            out.append(("shared", "-", share_a))
        else:
            custodian, other_share = ("B", share_a) if share_a < SHARED_MIN else ("A", 1 - share_a)
            kind = "exclusive" if other_share <= EXCLUSIVE_MAX else "extended"
            out.append((kind, custodian, other_share))
    return out


def compute_child_support(case: ChildSupportCase, params: dict | None = None) -> ChildSupportResult:
    """Remplit le formulaire de fixation pour `case` avec les paramètres de son année (ou `params`)."""
    p = (params or load_parameters(case.year))["pension_alimentaire"]
    f = Form("Formulaire de fixation des pensions alimentaires pour enfants")
    warnings: list[str] = []
    parents = {"A": case.parent_a, "B": case.parent_b}

    # Partie 2 — revenus annuels
    lines = [("200", "Salaire brut", "salary"), ("201", "Commissions/Pourboires", "commissions"),
             ("202", "Revenus nets d'entreprise ou de travail autonome", "business_income"),
             ("203", "Prestations d'assurance-emploi et d'assurance parentale", "ei_qpip_benefits"),
             ("204", "Pension alimentaire versée par un tiers et reçue à titre personnel", "support_received"),
             ("205", "Prestations de retraite, d'invalidité ou autres", "pension_benefits"),
             ("206", "Intérêts et dividendes et autres revenus de placements", "investment_income"),
             ("207", "Loyers nets", "net_rental_income"), ("208", "Autres revenus", "other_income")]
    total, disposable = {}, {}
    for x, inc in parents.items():
        for num, label, attr in lines:
            f.add(f"{num}.{x}", label, getattr(inc, attr))
        total[x] = f.add(f"209.{x}", "TOTAL (lignes 200 à 208)", sum(getattr(inc, a) for _, _, a in lines))

    # Partie 3 — revenu disponible
    for x, inc in parents.items():
        f.add(f"300.{x}", "Revenu annuel (ligne 209)", total[x])
        ded = f.add(f"301.{x}", "Déduction de base", p["basic_deduction"]["amount"], "selon la table de l'année")
        ded += f.add(f"302.{x}", "Déduction pour les cotisations syndicales", inc.union_dues)
        ded += f.add(f"303.{x}", "Déduction pour les cotisations professionnelles", inc.professional_dues)
        f.add(f"304.{x}", "Total des déductions (lignes 301 à 303)", ded)
        disposable[x] = f.add(f"305.{x}", "Revenu disponible de chaque parent", max(0.0, total[x] - ded),
                              "ligne 300 − ligne 304, 0 si négatif")
    both = f.add("306", "Revenu disponible des deux parents", disposable["A"] + disposable["B"])
    factor = {x: (disposable[x] / both if both > 0 else 0.5) for x in parents}
    for x in parents:
        f.add(f"307.{x}", "Facteur de répartition des revenus", factor[x], "ligne 305 / ligne 306 (fraction)")

    # Partie 4 — contribution alimentaire annuelle
    n = f.add("400", "Nombre d'enfants communs aux parents concernés par la demande", len(case.custody_days_a))
    n = int(n)
    base, above = base_contribution(both, n, p["base_contribution_table"])
    f.add("401", "Contribution alimentaire parentale de base", base,
          "table de l'année selon la ligne 306 et le nombre d'enfants")
    if above:
        warnings.append("Revenu disponible des parents au-delà de 200 000 $ : le pourcentage de l'excédent "
                        "n'est qu'indicatif, le tribunal peut fixer un autre montant (art. 10 du Règlement).")
    if n > 6:
        warnings.append("Plus de 6 enfants : montant extrapolé selon la note (1) de la table.")
    contrib = {x: f.add(f"402.{x}", "Contribution alimentaire parentale de base de chacun des parents",
                        base * factor[x], "ligne 401 × ligne 307") for x in parents}
    frais = f.add("403", "Frais de garde nets", case.childcare)
    frais += f.add("404", "Frais d'études postsecondaires nets", case.post_secondary)
    frais += f.add("405", "Frais particuliers nets", case.special_expenses)
    f.add("406", "Total des frais (lignes 403 à 405)", frais)
    frais_share = {x: f.add(f"407.{x}", "Contribution de chacun des parents aux frais", frais * factor[x],
                            "ligne 406 × ligne 307") for x in parents}

    # Partie 5 — pension selon le temps de garde
    kinds = _classify(case.custody_days_a)
    section, payable = _part5(f, kinds, base, frais, n, factor, contrib, frais_share)
    payer = next((x for x in parents if payable[x] > 0), None)

    # Partie 6 — capacité de payer du débiteur
    amount = 0.0
    if payer is not None:
        f.add("600", "Revenu disponible du parent devant payer la pension alimentaire", disposable[payer])
        cap = f.add("601", "Ligne 600 multipliée par 50 %", 0.5 * disposable[payer])
        due = f.add("602", "Pension alimentaire annuelle à payer selon la partie 5", payable[payer])
        amount = f.add("603", "Pension alimentaire annuelle à payer", min(cap, due),
                       "le moins élevé des lignes 601 et 602")
        if cap < due:
            warnings.append("Capacité de payer : la pension est plafonnée à 50 % du revenu disponible du débiteur.")
    return ChildSupportResult(case, f, section, payer, amount, tuple(warnings))


def _part5(f: Form, kinds, base, frais, n, factor, contrib, frais_share):
    """Choisit et remplit la section de la partie 5. Rend (section, pension à payer par parent)."""
    other = {"A": "B", "B": "A"}
    types = {k for k, _, _ in kinds}
    custodians = {c for k, c, _ in kinds if k != "shared"}
    payable = {"A": 0.0, "B": 0.0}

    if types == {"exclusive"} and len(custodians) == 1:                      # Section 1
        non = other[custodians.pop()]
        total = f.add("511", "Contribution alimentaire annuelle des deux parents", base + frais, "ligne 401 + ligne 406")
        payable[non] = f.add(f"512.{non}", "Pension alimentaire annuelle à payer par le parent non gardien",
                             total * factor[non], "ligne 511 × ligne 307")
        return "1", payable

    shares = {round(s, 9) for k, _, s in kinds if k == "extended"}
    if types == {"extended"} and len(custodians) == 1 and len(shares) == 1:  # Section 1.1
        non, pct = other[custodians.pop()], shares.pop()
        total = f.add("514", "Contribution alimentaire annuelle des deux parents", base + frais, "ligne 401 + ligne 406")
        f.add("515", "Pourcentage du temps de garde pour l'exercice du droit de visite et de sortie prolongé", pct)
        comp = f.add("516", "Compensation pour droit de visite et de sortie prolongé", (pct - EXCLUSIVE_MAX) * base,
                     "(ligne 515 − 20 %) × ligne 401")
        adjusted = f.add("517", "Contribution alimentaire annuelle ajustée des deux parents", total - comp)
        payable[non] = f.add(f"518.{non}", "Pension alimentaire annuelle à payer par le parent non gardien",
                             adjusted * factor[non], "ligne 517 × ligne 307")
        return "1.1", payable

    if types == {"exclusive"}:                                                # Section 2
        count = {x: sum(1 for k, c, _ in kinds if c == x) for x in ("A", "B")}
        f.add("520", "Nombre d'enfants sous la garde du parent A", count["A"])
        f.add("521", "Nombre d'enfants sous la garde du parent B", count["B"])
        cost = f.add("523", "Coût moyen par enfant", base / n, "ligne 401 / ligne 400")
        for x in ("A", "B"):
            f.add(f"522.{x}", "Contribution alimentaire parentale de base de chacun des parents", contrib[x])
            own = f.add(f"524.{x}", "Coût de la garde pour chaque parent", cost * count[x])
            net = f.add(f"525.{x}", "Pension alimentaire annuelle de base", max(0.0, contrib[x] - own))
            payable[x] = f.add(f"526.{x}", "Pension alimentaire annuelle à payer",
                               net + frais_share[x] if net > 0 else 0.0, "ligne 525 + ligne 407, 0 si 525 = 0")
        return "2", payable

    splits = {round(s, 9) for k, _, s in kinds if k == "shared"}
    if types == {"shared"} and len(splits) == 1:                              # Section 3
        share_a = splits.pop()
        split = {"A": share_a, "B": 1 - share_a}
        for x in ("A", "B"):
            f.add(f"530.{x}", "Facteur de répartition de la garde", split[x], "jours de garde / 365")
            f.add(f"531.{x}", "Contribution alimentaire parentale de base de chacun des parents", contrib[x])
            own = f.add(f"532.{x}", "Coût de la garde pour chaque parent", base * split[x], "ligne 401 × ligne 530")
            net = f.add(f"533.{x}", "Pension alimentaire annuelle de base", max(0.0, contrib[x] - own))
            payable[x] = f.add(f"534.{x}", "Pension alimentaire annuelle à payer",
                               net + frais_share[x] if net > 0 else 0.0, "ligne 533 + ligne 407, 0 si 533 = 0")
        return "3", payable

    return "4", _section4(f, kinds, base, n, factor, frais_share, payable)


def _section4(f: Form, kinds, base, n, factor, frais_share, payable):
    """Section 4 : garde exclusive, droit de visite prolongé et garde partagée simultanés."""
    other = {"A": "B", "B": "A"}
    ext = {x: {round(s, 9) for k, c, s in kinds if k == "extended" and other[c] == x} for x in ("A", "B")}
    splits = {round(s, 9) for k, _, s in kinds if k == "shared"}
    if any(len(v) > 1 for v in ext.values()) or len(splits) > 1:
        raise ValueError("section 4 : le formulaire n'admet qu'un pourcentage de droit de visite prolongé par "
                         "parent et un seul partage pour les enfants en garde partagée")
    cost = f.add("540", "Coût moyen par enfant", base / n, "ligne 401 / ligne 400")
    gap_excl, gap_ext, cost_ext, total = {}, {}, {}, {}
    for x in ("A", "B"):
        n_excl = f.add(f"541.{x}", "Nombre d'enfants concernés par la garde exclusive",
                       sum(1 for k, c, _ in kinds if k == "exclusive" and c == x))
        own = f.add(f"542.{x}", "Coût de la garde des enfants concernés par la garde exclusive", cost * n_excl)
        mine = f.add(f"543.{x}", "Contribution alimentaire de base du parent gardien", own * factor[x])
        gap_excl[x] = f.add(f"544.{x}", "Écart entre le coût de la garde et la contribution du parent gardien", own - mine)
    for x in ("A", "B"):
        f.add(f"545.{x}", "Pension alimentaire annuelle de base pour les enfants en garde exclusive",
              max(0.0, gap_excl[other[x]] - gap_excl[x]))
    for x in ("A", "B"):
        n_ext = f.add(f"546.{x}", "Nombre d'enfants concernés par la garde avec droit de visite et de sortie prolongé",
                      sum(1 for k, c, _ in kinds if k == "extended" and c == x))
        cost_ext[x] = f.add(f"547.{x}", "Coût de la garde des enfants concernés par la garde prolongée", cost * n_ext)
    for x in ("A", "B"):  # x exerce le droit prolongé sur les enfants gardés par l'autre parent
        pct = next(iter(ext[x]), EXCLUSIVE_MAX)
        f.add(f"548.{x}", "Pourcentage du temps de garde pour l'exercice du droit de visite et de sortie prolongé", pct)
        f.add(f"549.{x}", "Compensation pour droit de visite et de sortie prolongé",
              (pct - EXCLUSIVE_MAX) * cost_ext[other[x]], "(ligne 548 − 20 %) × ligne 547 de l'autre parent")
    for x in ("A", "B"):
        adjusted = f.add(f"550.{x}", "Coût de la garde des enfants concernés par la garde prolongée ajustée",
                         cost_ext[x] - f.amount(f"549.{other[x]}"))
        mine = f.add(f"551.{x}", "Contribution alimentaire annuelle de base du parent gardien", adjusted * factor[x])
        gap_ext[x] = f.add(f"552.{x}", "Écart entre le coût de la garde et la contribution alimentaire de base",
                           adjusted - mine)
    for x in ("A", "B"):
        f.add(f"553.{x}", "Pension alimentaire annuelle à payer pour la garde avec droit de visite et de sortie prolongé",
              max(0.0, gap_ext[other[x]] - gap_ext[x]))
    n_shared = f.add("554", "Nombre d'enfants concernés par la garde partagée",
                     sum(1 for k, _, _ in kinds if k == "shared"))
    shared_cost = f.add("555", "Coût de la garde des enfants concernés par la garde partagée", cost * n_shared)
    share_a = next(iter(splits), 0.5)
    split = {"A": share_a, "B": 1 - share_a}
    for x in ("A", "B"):
        f.add(f"556.{x}", "Facteur de répartition de la garde partagée", split[x])
        mine = f.add(f"557.{x}", "Contribution alimentaire parentale de base pour les enfants en garde partagée",
                     shared_cost * factor[x])
        own = f.add(f"558.{x}", "Coût de la garde partagée pour chaque parent", shared_cost * split[x])
        f.add(f"559.{x}", "Pension alimentaire annuelle de base pour les enfants en garde partagée", max(0.0, mine - own))
    for x in ("A", "B"):
        total[x] = (f.add(f"560.{x}", "Pension de base, enfants en garde exclusive", f.amount(f"545.{x}"))
                    + f.add(f"561.{x}", "Pension, garde avec droit de visite et de sortie prolongé", f.amount(f"553.{x}"))
                    + f.add(f"562.{x}", "Pension de base, enfants en garde partagée", f.amount(f"559.{x}")))
    for x in ("A", "B"):
        net = f.add(f"563.{x}", "Pension alimentaire annuelle de base totale", max(0.0, total[x] - total[other[x]]))
        payable[x] = f.add(f"564.{x}", "Pension alimentaire à payer", net + frais_share[x] if net > 0 else 0.0,
                           "ligne 563 + ligne 407, 0 si 563 = 0")
    return payable
