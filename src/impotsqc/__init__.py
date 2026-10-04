# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclarations de revenus T1 (fédérale) et TP-1 (Québec), ligne par ligne.

    >>> from impotsqc import Taxpayer, compute
    >>> r = compute(Taxpayer(year=2026, age=66, rrif_income=30_000, oas_pension=8_900))
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
from .model import Form, Line, Taxpayer, TaxReturn
from .parameters import PROVISIONAL_STATUSES, load_parameters
from .quebec import quebec_return

__version__ = "0.3.0"
__all__ = ["ChildSupportCase", "ChildSupportResult", "Form", "Line", "ParentIncome", "Taxpayer", "TaxReturn",
           "compute", "compute_child_support", "load_parameters"]

_PARAMS: dict[int, dict] = {}


def _params(year: int) -> dict:
    """Paramètres de l'année, chargés une seule fois (le moteur ne les modifie jamais)."""
    if year not in _PARAMS:
        _PARAMS[year] = load_parameters(year)
    return _PARAMS[year]


def compute(taxpayer: Taxpayer) -> TaxReturn:
    """Remplit les déclarations et les annexes applicables dans `TaxReturn.forms`."""
    params = _params(taxpayer.year)
    qpp = rules.qpp_contributions(taxpayer.employment_income, params["cotisations"]["qpp"])
    forms: dict[str, Form] = {}
    federal = federal_return(taxpayer, params, qpp, forms=forms)
    quebec_return(taxpayer, params, qpp, oas_repayment=federal.amount("23500"), forms=forms)
    return TaxReturn(taxpayer, forms, _warnings(taxpayer, params, forms))


def _warnings(tp: Taxpayer, params: dict, forms: dict[str, Form]) -> tuple[str, ...]:
    """Avertissements qui touchent CE contribuable : paramètres provisoires, règles dérivées, reports."""
    quebec = forms["TP-1"]
    out = []
    if params["quebec"]["drug_insurance"]["status"] in PROVISIONAL_STATUSES and quebec.amount("447") > 0:
        out.append(f"Ligne 447 (annexe K) : paramètres {tp.year} provisoires, non encore publiés.")
    if tp.age >= 65 and tp.employment_income > 0:
        out.append("RRQ : le choix de cesser de cotiser à 65 ans et plus n'est pas modélisé.")
    if "T691" in forms and forms["T691"].amount("P5-11") > 0:
        extra = forms["T691"].amount("P5-11")
        out.append(f"Impôt minimum fédéral : {extra:,.0f} $ d'impôt additionnel, reportable sur sept ans "
                   "(report non modélisé).")
    if "TP-1.D.E" in forms and forms["TP-1.D.E"].amount("15") > max(0.0, quebec.amount("430")):
        out.append("Impôt minimum du Québec : portée de calcul héritée du moteur 0.2; "
                   "report sur sept ans non modélisé.")
    return tuple(out)
