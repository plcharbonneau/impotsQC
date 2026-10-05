# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Règles élémentaires, communes à toutes les années : chaque fonction reçoit la table de
paramètres de l'année qui la concerne (p. ex. `params["federal"]["age_amount"]`).

Ce sont les briques des formulaires; l'assemblage ligne par ligne du T1 et du TP-1 viendra
au-dessus. Montants annuels en dollars, sans arrondi intermédiaire.
"""

from __future__ import annotations

from dataclasses import dataclass


def bracket_tax(income: float, table: dict) -> float:
    """Impôt selon un barème progressif (`thresholds` croissants, un taux de plus que de seuils)."""
    tax, lower = 0.0, 0.0
    for upper, rate in zip(table["thresholds"], table["rates"]):
        if income <= upper:
            return tax + (income - lower) * rate
        tax += (upper - lower) * rate
        lower = upper
    return tax + (income - lower) * table["rates"][-1]


def federal_basic_personal_amount(net_income: float, table: dict) -> float:
    """Montant personnel de base fédéral (ligne 30000) : la bonification décroît linéairement
    entre le début du 4e et celui du 5e palier, selon le revenu net."""
    hi, lo = table["maximum"], table["minimum"]
    start, end = table["phase_out_start"], table["phase_out_end"]
    if net_income <= start:
        return float(hi)
    if net_income >= end:
        return float(lo)
    return hi - (net_income - start) * (hi - lo) / (end - start)


def federal_age_amount(age: int, net_income: float, table: dict) -> float:
    """Montant en raison de l'âge (ligne 30100), réduit de 15 % du revenu net au-delà du seuil."""
    if age < table["minimum_age"]:
        return 0.0
    return max(0.0, table["amount"] - table["reduction_rate"] * max(0.0, net_income - table["threshold"]))


def oas_recovery(net_income_before_recovery: float, oas_received: float, table: dict) -> float:
    """Remboursement de la PSV (lignes 23500 et 42200), plafonné à la PSV reçue."""
    excess = max(0.0, net_income_before_recovery - table["threshold"])
    return min(oas_received, table["rate"] * excess)


@dataclass(frozen=True)
class QppContributions:
    """Cotisations RRQ d'un salarié : base (5,30 %), premier et deuxième supplémentaires."""

    base: float
    first_additional: float
    second_additional: float

    @property
    def total(self) -> float:
        """Cotisation totale retenue."""
        return self.base + self.first_additional + self.second_additional

    @property
    def enhanced(self) -> float:
        """Part bonifiée, déductible (fédéral ligne 22215, Québec ligne 248)."""
        return self.first_additional + self.second_additional


def qpp_contributions(employment_income: float, table: dict) -> QppContributions:
    """Cotisations RRQ sur un revenu d'emploi annuel (exemption de base appliquée)."""
    earnings = max(0.0, min(employment_income, table["maximum_pensionable_earnings"]) - table["basic_exemption"])
    above = max(0.0, min(employment_income, table["additional_maximum_pensionable_earnings"])
                - table["maximum_pensionable_earnings"])
    return QppContributions(earnings * table["base_rate"], earnings * table["first_additional_rate"],
                            above * table["second_additional_rate"])


def insurable_premium(employment_income: float, table: dict) -> float:
    """Cotisation plafonnée au maximum assurable (assurance-emploi, RQAP)."""
    return min(employment_income, table["maximum_insurable_earnings"]) * table["rate"]


def schedule_b_amount(*, age: int, lives_alone: bool, retirement_income: float, family_income: float,
                      table: dict) -> float:
    """Annexe B du TP-1 (ligne 361) : personne vivant seule, âge et revenus de retraite, moins
    18,75 % du revenu familial au-delà du seuil. `retirement_income` : lignes 122 et 123 seulement
    (PSV, RRQ et retraits forfaitaires REER exclus)."""
    total = table["living_alone"] if lives_alone else 0.0
    if age >= table["minimum_age"]:
        total += table["age"]
    total += min(table["retirement_income_factor"] * retirement_income, table["retirement_income_maximum"])
    return max(0.0, total - table["reduction_rate"] * max(0.0, family_income - table["reduction_threshold"]))


def health_services_fund(base: float, table: dict) -> float:
    """Cotisation au FSS (Annexe F). `base` exclut le revenu d'emploi, la PSV et la majoration
    des dividendes."""
    if base <= table["first_threshold"]:
        return 0.0
    if base <= table["second_threshold"]:
        return min(table["first_maximum"], table["rate"] * (base - table["first_threshold"]))
    return min(table["maximum"], table["first_maximum"] + table["rate"] * (base - table["second_threshold"]))


def grossed_up_dividends(eligible: float, other: float, table: dict) -> tuple[float, float]:
    """Montants imposables (majorés) des dividendes déterminés et ordinaires."""
    return eligible * (1 + table["eligible_gross_up"]), other * (1 + table["other_gross_up"])


def dividend_tax_credit(eligible_grossed_up: float, other_grossed_up: float, table: dict) -> tuple[float, float]:
    """Crédits pour dividendes (déterminés, ordinaires), en pourcentage du montant majoré."""
    return eligible_grossed_up * table["eligible_credit_rate"], other_grossed_up * table["other_credit_rate"]


def drug_insurance_exemption(*, has_spouse: bool, dependent_children: int, table: dict) -> float:
    """Exemption familiale de l'annexe K, selon le conjoint fiscal et les enfants admissibles."""
    status = "couple" if has_spouse else "single"
    exemption = table[f"exemption_{status}"]
    if dependent_children:
        count = "one" if dependent_children == 1 else "multiple"
        exemption += table[f"child_exemption_{status}_{count}"]
    return exemption


def drug_insurance_premium(family_income: float, table: dict, *, has_spouse: bool,
                           dependent_children: int, exempt_months: tuple[int, ...]) -> float:
    """Cotisation personnelle RAMQ : revenu familial, puis réduction pour les mois exemptés.

    Les mois (1 à 12, sans doublons) sont ceux de la partie B de l'annexe K, confirmés par
    l'appelant. Chacun paie sa propre cotisation; le choix de payer celle du conjoint est exclu.
    Les deux réductions utilisent respectivement 1/12 de la cotisation selon le revenu et
    les plafonds mensuels du semestre. Aucune couverture ni situation familiale n'est présumée.
    """
    if len(exempt_months) == 12:
        return 0.0
    x = family_income - drug_insurance_exemption(has_spouse=has_spouse,
                                                dependent_children=dependent_children, table=table)
    if x <= 0:
        return 0.0
    status = "couple" if has_spouse else "single"
    width = table["first_bracket_width"]
    if x <= width:
        premium = x * table[f"first_rate_{status}"]
    else:
        premium = width * table[f"first_rate_{status}"] + (x - width) * table[f"second_rate_{status}"]
    premium = min(premium, table["rate_cap"])
    reduced = premium - premium * len(exempt_months) / 12
    first = sum(month <= 6 for month in exempt_months)
    maximum = (table["annual_maximum"] - first * table["monthly_maximum_first_half"]
               - (len(exempt_months) - first) * table["monthly_maximum_second_half"])
    return max(0.0, min(reduced, maximum))


def career_extension_credit(*, age: int, work_income: float, net_income: float, table: dict) -> float:
    """Crédit pour prolongation de carrière (TP-1, ligne 391) : taux × revenu de travail au-delà de
    l'exclusion (plafonné), moins 7 % du revenu net au-delà du seuil. Nul avant l'âge minimal."""
    if age < table["minimum_age"]:
        return 0.0
    eligible = min(max(0.0, work_income - table["excluded_income"]), table["maximum_eligible_income"])
    reduction = table["reduction_rate"] * max(0.0, net_income - table["reduction_threshold"])
    return max(0.0, eligible * table["credit_rate"] - reduction)


@dataclass(frozen=True)
class MinimumTax:
    """Impôt minimum de remplacement : revenu imposable rajusté, partie au-delà de l'exemption,
    montant minimum (après crédits admis)."""

    adjusted_taxable_income: float
    net_adjusted_taxable_income: float
    minimum_amount: float


def minimum_tax(*, taxable_income: float, capital_gains: float, capital_gains_inclusion: float,
                addback_deductions: float, dividend_gross_up: float, credits: float, table: dict) -> MinimumTax:
    """IMR (T691 fédéral, TP-776.42 Québec), dans la portée du paquet : gains en capital inclus selon
    le taux de l'IMR, une fraction des déductions visées rajoutée, dividendes au montant réel
    (majoration retirée), crédits non remboursables admis selon la fraction de l'année."""
    gains_added = capital_gains * (table["capital_gains_inclusion"] - capital_gains_inclusion)
    adjusted = (taxable_income + gains_added + table["deduction_addback_rate"] * addback_deductions
                - dividend_gross_up)
    net = max(0.0, adjusted - table["exemption"])
    amount = max(0.0, table["rate"] * net - table["credit_fraction"] * credits)
    return MinimumTax(adjusted, net, amount)
