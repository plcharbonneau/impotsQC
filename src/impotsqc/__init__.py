# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclarations de revenus T1 (fédérale) et TP-1 (Québec), ligne par ligne.

    >>> from impotsqc import Taxpayer, compute
    >>> tp = Taxpayer(year=2026, age=66, rrif_income=30_000, oas_pension=8_900,
    ...               has_spouse=False, drug_plan_exempt_months=(), drug_plan_dependent_children=0)
    >>> r = compute(tp)
    >>> r.federal["23600"].amount, r.quebec["275"].amount   # revenus nets
    (38900.0, 38900.0)

Chaque résultat porte des avertissements (`warnings`) quand une règle provisoire ou non calculée
touche le contribuable : ils disent où la réponse peut s'écarter de la déclaration réelle.

`compute_child_support(ChildSupportCase)` remplit le formulaire de fixation des pensions
alimentaires pour enfants du Québec (module `child_support`).
"""

from __future__ import annotations

from . import rules
from .child_support import ChildSupportCase, ChildSupportResult, ParentIncome, compute_child_support
from .federal import federal_return
from .model import CoupleReturn, Form, Line, Taxpayer, TaxReturn
from .couple import compute_couple, required_couple_questions
from .inputs import Benefits, CoupleOptions, Deductions, PensionIncome, PensionSplit, TaxPayments
from .parameters import PROVISIONAL_STATUSES, load_parameters
from .payments import settle_tax_payments
from .quebec import quebec_return
from .questions import MissingInformationError, required_questions

__version__ = "0.6.0"
__all__ = ["PensionSplit", "TaxPayments", "CoupleOptions", "CoupleReturn", "compute_couple", "required_couple_questions", "Benefits", "Deductions", "PensionIncome", "ChildSupportCase", "ChildSupportResult", "Form", "Line", "ParentIncome", "Taxpayer", "TaxReturn",
           "MissingInformationError", "required_questions", "compute", "compute_child_support", "load_parameters"]

_PARAMS: dict[int, dict] = {}


def _params(year: int) -> dict:
    """Paramètres de l'année, chargés une seule fois (le moteur ne les modifie jamais)."""
    if year not in _PARAMS:
        _PARAMS[year] = load_parameters(year)
    return _PARAMS[year]


def compute(taxpayer: Taxpayer) -> TaxReturn:
    """Remplit les formulaires, ou lève `MissingInformationError` avec les questions à poser."""
    params = _params(taxpayer.year)
    questions = required_questions(taxpayer)
    if questions:
        raise MissingInformationError(questions)
    qpp = rules.qpp_contributions(taxpayer.employment_income, params["cotisations"]["qpp"])
    forms: dict[str, Form] = {}
    federal = federal_return(taxpayer, params, qpp, forms=forms)
    quebec_return(taxpayer, params, qpp, oas_repayment=federal.amount("23500"), forms=forms)
    if taxpayer.payments is not None:
        settle_tax_payments(taxpayer, forms)
    return TaxReturn(taxpayer, forms, _warnings(taxpayer, params, forms))


def _warnings(tp: Taxpayer, params: dict, forms: dict[str, Form], *, coordinated: bool = False) -> tuple[str, ...]:
    """Avertissements qui touchent CE contribuable : paramètres provisoires, règles dérivées, reports."""
    quebec = forms["TP-1"]
    out = []
    if params["quebec"]["drug_insurance"]["status"] in PROVISIONAL_STATUSES and len(tp.drug_plan_exempt_months) < 12:
        out.append(f"Ligne 447 (annexe K) : paramètres {tp.year} provisoires, non encore publiés.")
    if coordinated:
        out.append("Couple : revenus, annexe B et crédits fédéraux des annexes 2/5 coordonnés. "
                   "Les crédits pour autres personnes à charge, études et handicap ainsi que le "
                   "fractionnement des pensions particulières restent à compléter; le total reste incomplet. "
                   "Chaque conjoint paie sa propre cotisation RAMQ. Le partage de B n'est pas optimisé.")
    elif tp.has_spouse:
        out.append("Couple : la RAMQ utilise le revenu familial et le barème avec conjoint, "
                   "mais chacun paie sa propre cotisation. Les crédits et transferts entre conjoints "
                   "et le fractionnement de pension ne sont pas calculés. L'annexe B retient "
                   "seulement vos montants d'âge et de retraite, réduits selon le revenu familial; "
                   "les droits du conjoint et leur répartition ne sont pas calculés.")
    if (tp.age == 18 or tp.age >= 73) and tp.employment_income > 0:
        out.append("RRQ : prorata à 18 ans et fin des cotisations à 73 ans non modélisés; "
                   "calcul annuel hérité conservé, annexes 8 et U non produites pour cet âge.")
    if 65 <= tp.age < 73 and tp.employment_income > 0:
        out.append("RRQ : le choix de cesser de cotiser à 65 ans et plus n'est pas modélisé.")
    if "T691" in forms and forms["T691"].amount("P5-11") > 0:
        extra = forms["T691"].amount("P5-11")
        out.append(f"Impôt minimum fédéral : {extra:,.0f} $ d'impôt additionnel, reportable sur sept ans "
                   "(report non modélisé).")
    if "TP-1.D.E" in forms and forms["TP-1.D.E"].amount("15") > forms["TP-1.D.E"].amount("14"):
        out.append("Impôt minimum du Québec : impôt additionnel; "
                   "report sur sept ans non modélisé.")
    return tuple(out)
