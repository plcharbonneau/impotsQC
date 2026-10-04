# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclaration fédérale T1 d'un résident du Québec (formulaire 5005-R), ligne par ligne.

Numéros et libellés : 5005-R F (25), version 2025 du formulaire; la version 2026 n'est pas
publiée au 2026-10-04. Portée : voir `Taxpayer`. Sont nuls hors portée : impôt sur le revenu
fractionné (40424), report d'impôt minimum (40427), crédits pour impôt étranger, dons, frais
médicaux. L'impôt minimum de remplacement (T691) est calculé; son report sur sept ans ne l'est pas.
"""

from __future__ import annotations

from . import rules
from .model import Form, Taxpayer
from .rules import QppContributions


def federal_return(tp: Taxpayer, params: dict, qpp: QppContributions) -> Form:
    """Remplit le T1 de `tp` avec les paramètres de l'année et ses cotisations RRQ."""
    fed, cot = params["federal"], params["cotisations"]
    f = Form("T1")

    # Étape 2 — Revenu total
    eligible, other = rules.grossed_up_dividends(tp.eligible_dividends, tp.other_dividends, fed["dividends"])
    rrif_65 = tp.rrif_income if tp.age >= fed["pension_amount"]["minimum_age_for_rrif"] else 0.0
    incl = fed["capital_gains"]["inclusion_rate"]
    income = [
        f.add("10100", "Revenus d'emploi", tp.employment_income),
        f.add("11300", "Pension de la sécurité de la vieillesse (PSV)", tp.oas_pension),
        f.add("11400", "Prestations du RPC ou du RRQ", tp.qpp_benefits),
        f.add("11500", "Autres pensions et pensions de retraite", rrif_65, "FERR à 65 ans et plus"),
        f.add("12000", "Montant des dividendes (déterminés et autres que déterminés)", eligible + other,
              "dividendes réels majorés de 38 % (déterminés) et de 15 % (autres)"),
        f.add("12100", "Intérêts et autres revenus de placements", tp.interest_income),
        f.add("12700", "Gains en capital imposables", tp.capital_gains * incl, f"annexe 3 : gain × {incl:g}"),
        f.add("12900", "Revenus d'un régime enregistré d'épargne-retraite (REER)", tp.rrsp_income),
        f.add("13000", "Autres revenus", tp.rrif_income - rrif_65, "FERR avant 65 ans"),
    ]
    f.add("12010", "Montant des dividendes (autres que déterminés)", other, "inclus à la ligne 12000")
    total = f.add("15000", "Revenu total", sum(income))

    # Étapes 3 et 4 — Revenu net et revenu imposable
    deductions = f.add("20800", "Déduction pour REER", tp.rrsp_deduction)
    deductions += f.add("22215", "Déduction pour les cotisations bonifiées au RPC ou au RRQ sur un revenu d'emploi",
                        qpp.enhanced, "premier supplément (1/6,30 de la cotisation) + deuxième supplément")
    before = f.add("23400", "Revenu net avant rajustements", total - deductions)
    repayment = f.add("23500", "Remboursement des prestations de programmes sociaux",
                      rules.oas_recovery(before, tp.oas_pension, fed["oas_recovery"]),
                      "15 % de la ligne 23400 au-delà du seuil, plafonné à la PSV reçue")
    net = f.add("23600", "Revenu net", before - repayment)
    taxable = f.add("26000", "Revenu imposable", max(0.0, net))

    # Étape 5, partie B — Crédits d'impôt non remboursables
    amounts = [
        f.add("30000", "Montant personnel de base", rules.federal_basic_personal_amount(net, fed["basic_personal_amount"]),
              "bonification réduite linéairement entre les 4e et 5e paliers, selon la ligne 23600"),
        f.add("30100", "Montant en raison de l'âge", rules.federal_age_amount(tp.age, net, fed["age_amount"]),
              "65 ans et plus, moins 15 % de la ligne 23600 au-delà du seuil"),
        f.add("30800", "Cotisations de base au RPC ou au RRQ pour les revenus d'emploi", qpp.base, "taux de base de 5,30 %"),
        f.add("31200", "Cotisations de l'employé à l'assurance-emploi",
              rules.insurable_premium(tp.employment_income, cot["employment_insurance"]), "taux du Québec"),
        f.add("31205", "Cotisations au régime provincial d'assurance parentale (RPAP)",
              rules.insurable_premium(tp.employment_income, cot["qpip"])),
        f.add("31260", "Montant canadien pour emploi",
              min(fed["canada_employment_amount"]["maximum"], tp.employment_income)),
        f.add("31400", "Montant pour revenu de pension", min(fed["pension_amount"]["maximum"], rrif_65),
              "FERR à 65 ans et plus; PSV, RRQ et retraits REER exclus"),
    ]
    total_amounts = f.add("33500", "Total des montants", sum(amounts))
    credits = f.add("33800", "Montants multipliés par le taux du crédit", total_amounts * fed["credits"]["rate"])
    top = fed["top_up_credit"]
    credits += f.add("34990", "Crédit d'impôt compensatoire",
                     top["rate"] * max(0.0, total_amounts - top["amounts_threshold"]),
                     "garde 15 % sur les montants au-delà du 1er palier (2025-2030)")
    credits = f.add("35000", "Total des crédits d'impôt non remboursables fédéraux", credits)

    # Étape 5, parties A et C — Impôt fédéral net
    tax = f.add("40400", "Impôt fédéral sur le revenu imposable", rules.bracket_tax(taxable, fed["brackets"]),
                "partie A, barème de l'année; aucun impôt sur le revenu fractionné")
    dividend_credit = f.add("40425", "Crédit d'impôt fédéral pour dividendes",
                            sum(rules.dividend_tax_credit(eligible, other, fed["dividends"])),
                            "pourcentage du montant majoré, déterminés et autres")
    basic = f.add("42900", "Impôt fédéral de base", max(0.0, tax - credits - dividend_credit))
    federal_tax = f.add("40600", "Impôt fédéral", basic, "aucun crédit pour impôt étranger")

    # Formulaire T691 — impôt minimum de remplacement
    amt = rules.minimum_tax(taxable_income=taxable, capital_gains=tp.capital_gains, capital_gains_inclusion=incl,
                            addback_deductions=qpp.enhanced,
                            dividend_gross_up=(eligible - tp.eligible_dividends) + (other - tp.other_dividends),
                            credits=f.amount("33800"), table=fed["minimum_tax"])
    if amt.net_adjusted_taxable_income > 0:
        f.add("T691:93", "Revenu imposable rajusté", amt.adjusted_taxable_income,
              "revenu imposable + gains en capital à 100 % + 50 % de la ligne 22215 − majoration des dividendes")
        f.add("T691:95", "Revenu imposable rajusté net", amt.net_adjusted_taxable_income, "au-delà de l'exemption de base")
        f.add("T691:103", "Montant minimum", amt.minimum_amount, "taux × ligne 95 − 50 % de la ligne 33800")
    after_minimum = f.add("41700", "Impôt fédéral après l'impôt minimum", max(federal_tax, amt.minimum_amount),
                          "T691, partie 6 : le plus élevé de l'impôt fédéral et du montant minimum")
    net_tax = f.add("42000", "Impôt fédéral net", after_minimum)

    # Étape 6 — Total à payer et abattement du Québec
    f.add("42200", "Remboursement des prestations de programmes sociaux", repayment, "montant de la ligne 23500")
    f.add("43500", "Total à payer", net_tax + repayment)
    f.add("44000", "Abattement du Québec remboursable",
          max(basic, amt.minimum_amount) * fed["quebec_abatement"]["rate"],
          "16,5 % de la ligne 42900, ou du montant minimum s'il est plus élevé (T691, note 14)")
    return f
