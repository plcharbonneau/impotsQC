# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclaration fédérale T1 d'un résident du Québec (formulaire 5005-R), ligne par ligne.

Numéros et libellés : 5005-R F (25), version 2025 du formulaire; la version 2026 n'est pas
publiée au 2026-10-04. Portée : voir `Taxpayer`. Sont nuls hors portée : impôt sur le revenu
fractionné (40424), report d'impôt minimum (40427), crédits pour impôt étranger, dons, frais
médicaux. L'impôt minimum de remplacement (T691) est calculé; son report sur sept ans ne l'est pas.
"""

from __future__ import annotations

from . import federal_schedules, rules
from .model import Form, Taxpayer
from .rules import QppContributions


def federal_return(tp: Taxpayer, params: dict, qpp: QppContributions, *, forms: dict[str, Form]) -> Form:
    """Remplit le T1 de `tp` avec les paramètres de l'année et ses cotisations RRQ."""
    fed, cot = params["federal"], params["cotisations"]
    f = Form.from_parameters("T1", params)
    forms[f.code] = f

    # Étape 2 — Revenu total
    eligible, other = rules.grossed_up_dividends(tp.eligible_dividends, tp.other_dividends, fed["dividends"])
    rrif_65 = tp.rrif_income if tp.age >= fed["pension_amount"]["minimum_age_for_rrif"] else 0.0
    annex_3 = federal_schedules.capital_gains(tp, params)
    if annex_3 is not None:
        forms[annex_3.code] = annex_3
    income = [
        f.add("10100", "Revenus d'emploi", tp.employment_income),
        f.add("11300", "Pension de la sécurité de la vieillesse (PSV)", tp.oas_pension),
        f.add("11400", "Prestations du RPC ou du RRQ", tp.qpp_benefits),
        f.add("11500", "Autres pensions et pensions de retraite", rrif_65, "FERR à 65 ans et plus",
              params=("federal.pension_amount.minimum_age_for_rrif",)),
        f.add("12000", "Montant des dividendes (déterminés et autres que déterminés)", eligible + other,
              "dividendes réels majorés de 38 % (déterminés) et de 15 % (autres)",
              params=("federal.dividends.eligible_gross_up", "federal.dividends.other_gross_up")),
        f.add("12100", "Intérêts et autres revenus de placements", tp.interest_income),
        f.add("12700", "Gains en capital imposables", annex_3.amount("19900") if annex_3 is not None else 0.0,
              "annexe 3, ligne 19900 si applicable", refs=("5000-S3:19900",) if annex_3 is not None else ()),
        f.add("12900", "Revenus d'un régime enregistré d'épargne-retraite (REER)", tp.rrsp_income),
        f.add("13000", "Autres revenus", tp.rrif_income - rrif_65, "FERR avant 65 ans",
              params=("federal.pension_amount.minimum_age_for_rrif",)),
    ]
    f.add("12010", "Montant des dividendes (autres que déterminés)", other, "inclus à la ligne 12000",
          params=("federal.dividends.other_gross_up",))
    total = f.add("15000", "Revenu total", sum(income),
                  refs=(
                      "T1:10100",
                      "T1:11300",
                      "T1:11400",
                      "T1:11500",
                      "T1:12000",
                      "T1:12100",
                      "T1:12700",
                      "T1:12900",
                      "T1:13000",
                  ))

    annex_8 = federal_schedules.qpp_employment(tp, params, qpp)
    if annex_8 is not None:
        forms[annex_8.code] = annex_8

    # Étapes 3 et 4 — Revenu net et revenu imposable
    deductions = f.add("20800", "Déduction pour REER", tp.rrsp_deduction)
    deductions += f.add("22215", "Déduction pour les cotisations bonifiées au RPC ou au RRQ sur un revenu d'emploi",
                        annex_8.amount("P2-47") if annex_8 is not None else qpp.enhanced,
                        "annexe 8, partie 2, ligne 47 si applicable",
                        refs=("5005-S8:P2-47",) if annex_8 is not None else (),
                        params=(
                            "cotisations.qpp.basic_exemption",
                            "cotisations.qpp.maximum_pensionable_earnings",
                            "cotisations.qpp.additional_maximum_pensionable_earnings",
                            "cotisations.qpp.first_additional_rate",
                            "cotisations.qpp.second_additional_rate",
                        ))
    before = f.add("23400", "Revenu net avant rajustements", total - deductions,
                   refs=("T1:15000", "T1:20800", "T1:22215"))
    repayment = f.add("23500", "Remboursement des prestations de programmes sociaux",
                      rules.oas_recovery(before, tp.oas_pension, fed["oas_recovery"]),
                      "15 % de la ligne 23400 au-delà du seuil, plafonné à la PSV reçue",
                      refs=("T1:23400", "T1:11300"),
                      params=("federal.oas_recovery.threshold", "federal.oas_recovery.rate"))
    net = f.add("23600", "Revenu net", before - repayment,
                refs=("T1:23400", "T1:23500"))
    taxable = f.add("26000", "Revenu imposable", max(0.0, net),
                    refs=("T1:23600",))

    # Étape 5, partie B — Crédits d'impôt non remboursables
    amounts = [
        f.add("30000", "Montant personnel de base", rules.federal_basic_personal_amount(net, fed["basic_personal_amount"]),
              "bonification réduite linéairement entre les 4e et 5e paliers, selon la ligne 23600",
              refs=("T1:23600",),
              params=(
                  "federal.basic_personal_amount.maximum",
                  "federal.basic_personal_amount.minimum",
                  "federal.basic_personal_amount.phase_out_start",
                  "federal.basic_personal_amount.phase_out_end",
              )),
        f.add("30100", "Montant en raison de l'âge", rules.federal_age_amount(tp.age, net, fed["age_amount"]),
              "65 ans et plus, moins 15 % de la ligne 23600 au-delà du seuil",
              refs=("T1:23600",),
              params=(
                  "federal.age_amount.amount",
                  "federal.age_amount.threshold",
                  "federal.age_amount.reduction_rate",
                  "federal.age_amount.minimum_age",
              )),
        f.add("30800", "Cotisations de base au RPC ou au RRQ pour les revenus d'emploi",
              annex_8.amount("P2-35") if annex_8 is not None else qpp.base,
              "annexe 8, partie 2, ligne 35 si applicable",
              refs=("5005-S8:P2-35",) if annex_8 is not None else (),
              params=(
                  "cotisations.qpp.basic_exemption",
                  "cotisations.qpp.maximum_pensionable_earnings",
                  "cotisations.qpp.base_rate",
              )),
        f.add("31200", "Cotisations de l'employé à l'assurance-emploi",
              rules.insurable_premium(tp.employment_income, cot["employment_insurance"]), "taux du Québec",
              refs=("T1:10100",),
              params=(
                  "cotisations.employment_insurance.maximum_insurable_earnings",
                  "cotisations.employment_insurance.rate",
              )),
        f.add("31205", "Cotisations au régime provincial d'assurance parentale (RPAP)",
              rules.insurable_premium(tp.employment_income, cot["qpip"]),
              refs=("T1:10100",),
              params=("cotisations.qpip.maximum_insurable_earnings", "cotisations.qpip.rate")),
        f.add("31260", "Montant canadien pour emploi",
              min(fed["canada_employment_amount"]["maximum"], tp.employment_income),
              refs=("T1:10100",),
              params=("federal.canada_employment_amount.maximum",)),
        f.add("31400", "Montant pour revenu de pension", min(fed["pension_amount"]["maximum"], rrif_65),
              "FERR à 65 ans et plus; PSV, RRQ et retraits REER exclus",
              refs=("T1:11500",),
              params=("federal.pension_amount.maximum",)),
    ]
    total_amounts = f.add("33500", "Total des montants", sum(amounts),
                          refs=("T1:30000", "T1:30100", "T1:30800", "T1:31200", "T1:31205", "T1:31260", "T1:31400"))
    credits = f.add("33800", "Montants multipliés par le taux du crédit", total_amounts * fed["credits"]["rate"],
                    refs=("T1:33500",),
                    params=("federal.credits.rate",))
    top = fed["top_up_credit"]
    credits += f.add("34990", "Crédit d'impôt compensatoire",
                     top["rate"] * max(0.0, total_amounts - top["amounts_threshold"]),
                     "garde 15 % sur les montants au-delà du 1er palier (2025-2030)",
                     refs=("T1:33500",),
                     params=("federal.top_up_credit.rate", "federal.top_up_credit.amounts_threshold"))
    credits = f.add("35000", "Total des crédits d'impôt non remboursables fédéraux", credits,
                    refs=("T1:33800", "T1:34990"))

    # Étape 5, parties A et C — Impôt fédéral net
    tax = f.add("40400", "Impôt fédéral sur le revenu imposable", rules.bracket_tax(taxable, fed["brackets"]),
                "partie A, barème de l'année; aucun impôt sur le revenu fractionné",
                refs=("T1:26000",),
                params=("federal.brackets.thresholds", "federal.brackets.rates"))
    dividend_credit = f.add("40425", "Crédit d'impôt fédéral pour dividendes",
                            sum(rules.dividend_tax_credit(eligible, other, fed["dividends"])),
                            "pourcentage du montant majoré, déterminés et autres",
                            refs=("T1:12000", "T1:12010"),
                            params=("federal.dividends.eligible_credit_rate", "federal.dividends.other_credit_rate"))
    basic = f.add("42900", "Impôt fédéral de base", max(0.0, tax - credits - dividend_credit),
                  refs=("T1:40400", "T1:35000", "T1:40425"))
    federal_tax = f.add("40600", "Impôt fédéral", basic, "aucun crédit pour impôt étranger",
                        refs=("T1:42900",))

    # T691 : le formulaire n'est construit que si l'exemption est dépassée.
    annex = federal_schedules.minimum_tax(tp, params, f,
        dividend_gross_up=(eligible - tp.eligible_dividends) + (other - tp.other_dividends))
    minimum = 0.0
    if annex is not None:
        forms[annex.code] = annex
        minimum = annex.amount("P1-103")
    after_minimum = f.add("41700", "Impôt fédéral après l'impôt minimum", max(federal_tax, minimum),
                          "le plus élevé de l'impôt fédéral et du montant minimum",
                          refs=("T1:40600", "T691:P1-103") if annex is not None else ("T1:40600",))
    net_tax = f.add("42000", "Impôt fédéral net", after_minimum,
                    refs=("T1:41700",))

    # Étape 6 — Total à payer et abattement du Québec
    f.add("42200", "Remboursement des prestations de programmes sociaux", repayment, "montant de la ligne 23500",
          refs=("T1:23500",))
    f.add("43500", "Total à payer", net_tax + repayment,
          refs=("T1:42000", "T1:42200"))
    f.add("44000", "Abattement du Québec remboursable",
          max(basic, minimum) * fed["quebec_abatement"]["rate"],
          "16,5 % de la ligne 42900, ou du montant minimum s'il est plus élevé (T691, note 14)",
          refs=("T1:42900", "T691:P1-103") if annex is not None else ("T1:42900",),
          params=("federal.quebec_abatement.rate",))
    return f
