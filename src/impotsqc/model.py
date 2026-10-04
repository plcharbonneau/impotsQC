# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Entrées (contribuable) et sorties (formulaires remplis, ligne par ligne)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass(frozen=True)
class Taxpayer:
    """Contribuable fictif, résident du Québec au 31 décembre, sans conjoint.

    Montants annuels en dollars de l'année `year`. `age` est l'âge au 31 décembre.
    - `rrif_income` : retraits d'un FERR ou d'un FRV (ligne 11500 à 65 ans et plus, 13000 avant);
    - `rrsp_income` : retraits d'un REER (ligne 12900; TP-1 ligne 122);
    - `eligible_dividends`, `other_dividends` : montants RÉELS, avant majoration;
    - `capital_gains` : gain en capital net réalisé, avant inclusion.
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
    lives_alone: bool = False

    def __post_init__(self) -> None:
        """Refuse les montants négatifs et les âges hors d'une vie adulte."""
        if not 18 <= self.age <= 120:
            raise ValueError(f"âge hors de [18, 120] : {self.age}")
        for f in fields(self):
            value = getattr(self, f.name)
            if f.type == "float" and value < 0:
                raise ValueError(f"{f.name} ne peut pas être négatif : {value}")


@dataclass(frozen=True)
class Line:
    """Une ligne de formulaire : numéro officiel, libellé officiel, montant, règle appliquée."""

    number: str
    label: str
    amount: float
    rule: str = ""


@dataclass
class Form:
    """Formulaire rempli (`"T1"` ou `"TP-1"`), lignes dans l'ordre de calcul.

    Les montants ne sont pas arrondis : la fonction d'impôt reste continue, ce que demandent les
    recherches de racine de `retraiteqc`. `to_dict()` arrondit au cent pour l'affichage.
    """

    name: str
    lines: dict[str, Line] = field(default_factory=dict)

    def add(self, number: str, label: str, amount: float, rule: str = "") -> float:
        """Inscrit une ligne et rend son montant."""
        self.lines[number] = Line(number, label, float(amount), rule)
        return float(amount)

    def __getitem__(self, number: str) -> Line:
        """La ligne `number` (KeyError si elle n'a pas été remplie)."""
        return self.lines[number]

    def amount(self, number: str) -> float:
        """Montant de la ligne `number`, 0 si elle n'a pas été remplie."""
        line = self.lines.get(number)
        return line.amount if line else 0.0

    def to_dict(self) -> dict[str, dict]:
        """`{numéro: {"label", "amount", "rule"}}`, montants au cent."""
        return {n: {"label": l.label, "amount": round(l.amount, 2), "rule": l.rule} for n, l in self.lines.items()}


@dataclass(frozen=True)
class TaxReturn:
    """Déclarations fédérale et québécoise d'un contribuable, avec les avertissements de calcul."""

    taxpayer: Taxpayer
    federal: Form
    quebec: Form
    warnings: tuple[str, ...] = ()

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
        return {
            "year": self.taxpayer.year,
            "taxpayer": asdict(self.taxpayer),
            "federal": self.federal.to_dict(),
            "quebec": self.quebec.to_dict(),
            "summary": {k: round(getattr(self, k), 2) for k in
                        ("federal_payable", "quebec_payable", "payroll_contributions", "total_payable")},
            "warnings": list(self.warnings),
        }
