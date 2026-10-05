# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Entrées (contribuable) et sorties (formulaires remplis, ligne par ligne)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import NamedTuple

from .inputs import Benefits, Deductions, PensionIncome, validate_amounts


@dataclass(frozen=True)
class Taxpayer:
    """Contribuable fictif, résident du Québec au 31 décembre.

    Montants annuels en dollars de l'année `year`. `age` est l'âge au 31 décembre.
    - `rrif_income` : retraits d'un FERR ou d'un FRV (ligne 11500 à 65 ans et plus, 13000 avant);
    - `rrsp_income` : retraits ordinaires d’un REER non échu (ligne 12900; TP-1 ligne 154);
    - `eligible_dividends`, `other_dividends` : montants RÉELS, avant majoration;
    - `capital_gains` : gain en capital net réalisé, avant inclusion.
    - `has_spouse` : conjoint fiscal au 31 décembre selon Revenu Québec, distinct de `lives_alone`;
    - `spouse_net_income` : revenu net du conjoint au Québec (TP-1, ligne 275), même s'il est nul;
    - `drug_plan_exempt_months` : mois exemptés de cotisation RAMQ (1 à 12), régime privé de
      base ou autre exemption confirmée; `()` signifie aucune exemption, `None` signifie inconnu;
    - `drug_plan_dependent_children` : enfants à charge admissibles à l'annexe K, zéro à confirmer.

    `lives_alone` confirme l’admissibilité annuelle au montant pour personne vivant seule,
    et non simplement l’absence d’un conjoint dans l’habitation au 31 décembre.
    Les questions manquantes sont exposées par `required_questions`; `compute` les exige avant
    de produire un total. `compute_couple` coordonne les revenus et le partage de l’annexe B;
    les autres crédits/transferts entre conjoints restent signalés hors portée. Chaque conjoint
    paie sa propre cotisation RAMQ.
    """

    year: int
    age: int
    employment_income: float = 0.0
    oas_pension: float = 0.0
    qpp_benefits: float = 0.0
    rrif_income: float = 0.0
    rrsp_income: float = 0.0
    interest_income: float = 0.0
    eligible_dividends: float = 0.0
    other_dividends: float = 0.0
    capital_gains: float = 0.0
    rrsp_deduction: float = 0.0
    pensions: tuple[PensionIncome, ...] = ()
    benefits: Benefits | None = None
    deductions: Deductions | None = None
    lives_alone: bool = False
    has_spouse: bool | None = None
    spouse_net_income: float | None = None
    drug_plan_exempt_months: tuple[int, ...] | None = None
    drug_plan_dependent_children: int | None = None

    def __post_init__(self) -> None:
        """Valide les montants, l’âge adulte et les réponses explicites sur le ménage et les mois."""
        if not 18 <= self.age <= 120:
            raise ValueError(f"âge hors de [18, 120] : {self.age}")
        validate_amounts(self)
        if self.benefits is not None and not isinstance(self.benefits, Benefits):
            raise ValueError("benefits doit être un objet Benefits")
        if self.deductions is not None and not isinstance(self.deductions, Deductions):
            raise ValueError("deductions doit être un objet Deductions")
        if not isinstance(self.pensions, (tuple, list)) or any(
                not isinstance(pension, PensionIncome) for pension in self.pensions):
            raise ValueError("pensions doit contenir des objets PensionIncome")
        object.__setattr__(self, "pensions", tuple(self.pensions))
        if self.has_spouse is not None and type(self.has_spouse) is not bool:
            raise ValueError("has_spouse doit être True, False ou None (inconnu)")
        if self.spouse_net_income is not None:
            value = self.spouse_net_income
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError("spouse_net_income doit être un montant fini et non négatif")
            if self.has_spouse is False:
                raise ValueError("spouse_net_income est incompatible avec has_spouse=False")
        children = self.drug_plan_dependent_children
        if children is not None and (type(children) is not int or children < 0):
            raise ValueError("drug_plan_dependent_children doit être un entier non négatif")
        months = self.drug_plan_exempt_months
        if months is not None:
            if not isinstance(months, (tuple, list)) or any(type(m) is not int or not 1 <= m <= 12 for m in months):
                raise ValueError("drug_plan_exempt_months doit contenir des mois entiers de 1 à 12")
            if len(set(months)) != len(months):
                raise ValueError("drug_plan_exempt_months ne peut pas contenir de doublons")
            object.__setattr__(self, "drug_plan_exempt_months", tuple(sorted(months)))


class Line(NamedTuple):
    """Une ligne de formulaire : numéro officiel, libellé officiel, montant, règle appliquée."""

    number: str
    label: str
    amount: float
    rule: str = ""
    refs: tuple[str, ...] = ()
    params: tuple[str, ...] = ()


@dataclass
class Form:
    """Formulaire ou annexe rempli, identifié par son code officiel.

    Les montants ne sont pas arrondis : la fonction d'impôt reste continue, ce que demandent les
    recherches de racine de `retraiteqc`. `to_dict()` arrondit au cent pour l'affichage.
    """

    code: str
    lines: dict[str, Line] = field(default_factory=dict)
    title: str = ""
    version: str = ""
    source: str = ""

    @classmethod
    def from_parameters(cls, code: str, params: dict) -> Form:
        """Crée un formulaire vide avec les métadonnées de l'année, sans copier les paramètres."""
        meta = params["formulaires"][code]
        return cls(code, title=meta["title"], version=meta["version"], source=meta["source"])

    @property
    def name(self) -> str:
        """Alias historique de `code`."""
        return self.code

    def add(self, number: str, label: str, amount: float, rule: str = "", *,
            refs: tuple[str, ...] = (), params: tuple[str, ...] = ()) -> float:
        """Inscrit une ligne et rend son montant."""
        amount = float(amount)
        self.lines[number] = Line(number, label, amount, rule, refs, params)
        return amount

    def __getitem__(self, number: str) -> Line:
        """La ligne `number` (KeyError si elle n'a pas été remplie)."""
        return self.lines[number]

    def amount(self, number: str) -> float:
        """Montant de la ligne `number`, 0 si elle n'a pas été remplie."""
        line = self.lines.get(number)
        return line.amount if line else 0.0

    def to_dict(self) -> dict:
        """Métadonnées et lignes sérialisables en JSON; montants au cent, liens conservés."""
        return {"title": self.title, "version": self.version, "source": self.source,
                "lines": {n: {"label": l.label, "amount": round(l.amount, 2), "rule": l.rule,
                              "refs": list(l.refs), "params": list(l.params)} for n, l in self.lines.items()}}


@dataclass(frozen=True)
class TaxReturn:
    """Déclarations fédérale et québécoise d'un contribuable, avec les avertissements de calcul."""

    taxpayer: Taxpayer
    forms: dict[str, Form]
    warnings: tuple[str, ...] = ()

    @property
    def federal(self) -> Form:
        """Alias de `forms["T1"]`, conservé pour les utilisateurs de l'API historique."""
        return self.forms["T1"]

    @property
    def quebec(self) -> Form:
        """Alias de `forms["TP-1"]`, conservé pour les utilisateurs de l'API historique."""
        return self.forms["TP-1"]

    @property
    def federal_payable(self) -> float:
        """Impôt fédéral à payer, abattement remboursable du Québec déduit (lignes 43500 − 44000)."""
        return self.federal.amount("43500") - self.federal.amount("44000")

    @property
    def quebec_payable(self) -> float:
        """Impôt et cotisations du Québec (TP-1, ligne 450)."""
        return self.quebec.amount("450")

    @property
    def payroll_contributions(self) -> float:
        """Cotisations retenues sur la paie : RRQ (lignes 98 et 98.2), RQAP (97), AE (T1 31200)."""
        return (self.quebec.amount("98") + self.quebec.amount("98.2") + self.quebec.amount("97")
                + self.federal.amount("31200"))

    @property
    def total_payable(self) -> float:
        """Impôts fédéral et du Québec, cotisations sociales comprises."""
        return self.federal_payable + self.quebec_payable + self.payroll_contributions

    def to_dict(self) -> dict:
        """Déclaration complète en JSON simple, pour un script ou un agent."""
        forms = {code: form.to_dict() for code, form in self.forms.items()}
        return {
            "year": self.taxpayer.year,
            "taxpayer": asdict(self.taxpayer),
            "forms": forms,
            # Compatibilité 0.3 : les deux dictionnaires de lignes historiques restent disponibles.
            "federal": forms["T1"]["lines"],
            "quebec": forms["TP-1"]["lines"],
            "summary": {k: round(getattr(self, k), 2) for k in
                        ("federal_payable", "quebec_payable", "payroll_contributions", "total_payable")},
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CoupleReturn:
    """Deux déclarations coordonnées, avec les liens entre personnes séparés des liens locaux.

    Les clés de `refs` sont de la forme `first/TP-1.D.B:12`; elles désignent les lignes qui
    consultent la déclaration `first` ou `second`. Chaque `TaxReturn` conserve ses codes
    officiels et ses références locales `CODE:ligne`.
    """

    first: TaxReturn
    second: TaxReturn
    refs: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def total_payable(self) -> float:
        """Somme des impôts et cotisations des deux déclarations, dans la portée calculée."""
        return self.first.total_payable + self.second.total_payable

    def to_dict(self) -> dict:
        """Sérialise les deux déclarations et les dépendances entre conjoints en JSON simple."""
        return {"year": self.first.taxpayer.year,
                "first": self.first.to_dict(), "second": self.second.to_dict(),
                "refs": {key: list(values) for key, values in self.refs.items()},
                "summary": {"total_payable": round(self.total_payable, 2)}}
