# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""T691 : parties utiles au calcul courant, numéros préfixés par la partie du document."""

from __future__ import annotations

from . import rules
from .model import Form, Taxpayer


def minimum_tax(tp: Taxpayer, params: dict, federal: Form, dividend_gross_up: float) -> Form | None:
    """Remplit le T691 si le revenu rajusté dépasse l'exemption, sans modifier la règle de 0.2."""
    t = params["federal"]["minimum_tax"]
    inclusion = params["federal"]["capital_gains"]["inclusion_rate"]
    taxable, enhanced = federal.amount("26000"), federal.amount("22215")
    amt = rules.minimum_tax(taxable_income=taxable, capital_gains=tp.capital_gains, capital_gains_inclusion=inclusion,
                            addback_deductions=enhanced, dividend_gross_up=dividend_gross_up,
                            credits=federal.amount("33800"), table=t)
    if amt.net_adjusted_taxable_income <= 0:
        return None
    f = Form.from_parameters("T691", params)
    f.add("P1-1", "Revenu imposable", taxable, "base du moteur 0.2, après plancher à zéro",
          refs=("T1:26000",))
    gains = f.add("P1-23", "Partie non imposable des gains en capital", tp.capital_gains * (t["capital_gains_inclusion"] - inclusion),
                  "gain réalisé × différence des taux d'inclusion",
                  refs=("T1:12700",),
                  params=("federal.capital_gains.inclusion_rate", "federal.minimum_tax.capital_gains_inclusion"))
    f.add("P1-58", "Déduction pour les cotisations bonifiées au RPC ou au RRQ", enhanced,
          refs=("T1:22215",))
    addback = f.add("P1-80", "Déductions rajoutées", t["deduction_addback_rate"] * enhanced, "déductions visées dans la portée",
                    refs=("T691:P1-58",),
                    params=("federal.minimum_tax.deduction_addback_rate",))
    f.add("P1-83", "Revenu avant réductions", taxable + gains + addback, "lignes 1 + 23 + 80 dans la portée",
          refs=("T691:P1-1", "T691:P1-23", "T691:P1-80"))
    f.add("P1-86", "Majoration des dividendes", dividend_gross_up, "montant imposable moins dividendes réels",
          refs=("T1:12000", "T1:12010"),
          params=("federal.dividends.eligible_gross_up", "federal.dividends.other_gross_up"))
    f.add("P1-93", "Revenu imposable rajusté", amt.adjusted_taxable_income, "ligne 83 − ligne 86 dans la portée",
          refs=("T691:P1-83", "T691:P1-86"))
    f.add("P1-94", "Exemption de base", t["exemption"],
          params=("federal.minimum_tax.exemption",))
    f.add("P1-95", "Revenu imposable net rajusté", amt.net_adjusted_taxable_income, "ligne 93 − ligne 94, minimum zéro",
          refs=("T691:P1-93", "T691:P1-94"))
    f.add("P1-96", "Taux d'impôt fédéral", t["rate"], "taux exprimé comme fraction",
          params=("federal.minimum_tax.rate",))
    f.add("P1-97", "Montant minimum brut", t["rate"] * amt.net_adjusted_taxable_income,
          refs=("T691:P1-95", "T691:P1-96"))
    credits = f.add("P1-98", "Crédits d'impôt non remboursables nets", t["credit_fraction"] * federal.amount("33800"),
                    refs=("T1:33800",),
                    params=("federal.minimum_tax.credit_fraction",))
    f.add("P1-102", "Total des crédits admis", credits, "aucun autre crédit visé dans la portée",
          refs=("T691:P1-98",))
    f.add("P1-103", "Montant minimum", amt.minimum_amount, "ligne 97 − ligne 102, minimum zéro",
          refs=("T691:P1-97", "T691:P1-102"))
    f.add("P5-1", "Montant minimum", amt.minimum_amount,
          refs=("T691:P1-103",))
    ordinary = f.add("P5-4", "Impôt fédéral ordinaire net à payer", federal.amount("40600"),
                     "aucun crédit étranger, surtaxe ni crédit d'investissement dans la portée",
                     refs=("T1:40600",))
    extra = f.add("P5-11", "Impôt minimum additionnel", max(0.0, amt.minimum_amount - ordinary),
                  "lignes 1 − 4 dans la portée, minimum zéro",
                  refs=("T691:P5-1", "T691:P5-4"))
    if extra > 0:
        f.add("P6-3", "Impôt fédéral de base hors revenu fractionné", federal.amount("42900"),
              refs=("T1:42900",))
        f.add("P6-4", "Montant minimum", amt.minimum_amount,
              refs=("T691:P1-103",))
        f.add("P6-7", "Impôt fédéral de base aux fins de l'abattement", max(federal.amount("42900"), amt.minimum_amount),
              "aucun impôt sur le revenu fractionné",
              refs=("T691:P6-3", "T691:P6-4"))
        f.add("P6-14", "Impôt fédéral à payer dans le cadre de l'IMR", amt.minimum_amount,
              "aucune surtaxe ni impôt sur le revenu fractionné",
              refs=("T691:P6-4",))
    return f
