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
from .pensions import pension_amounts
from .rules import QppContributions


def federal_return(tp: Taxpayer, params: dict, qpp: QppContributions, *, forms: dict[str, Form]) -> Form:
    """Remplit le T1 de `tp` avec les paramètres de l'année et ses cotisations RRQ."""
    federal_income(tp, params, qpp, forms=forms)
    federal_personal_credits(tp, params, qpp, forms=forms)
    return federal_tax(tp, params, forms=forms)


def federal_income(tp: Taxpayer, params: dict, qpp: QppContributions, *, forms: dict[str, Form],
                   split_recipient: bool = False) -> Form:
    """Remplit les revenus et déductions du T1 avant toute attribution de crédits familiaux."""
    fed = params["federal"]
    f = Form.from_parameters("T1", params)
    forms[f.code] = f

    # Étape 2 — Revenu total
    eligible, other = rules.grossed_up_dividends(tp.eligible_dividends, tp.other_dividends, fed["dividends"])
    pension_income, rrsp_annuities, other_rrif, eligible_annuity = pension_amounts(tp, params)
    annex_3 = federal_schedules.capital_gains(tp, params)
    if annex_3 is not None:
        forms[annex_3.code] = annex_3
    income = [
        f.add("10100", "Revenus d'emploi", tp.employment_income),
        f.add("11300", "Pension de la sécurité de la vieillesse (PSV)", tp.oas_pension),
        f.add("11400", "Prestations du RPC ou du RRQ", tp.qpp_benefits),
        f.add("11500", "Autres pensions et pensions de retraite", pension_income, "rentes de RPA; FERR à 65 ans et plus ou reçus en raison du décès du conjoint",
              params=("federal.pension_amount.minimum_age_for_rrif",)),
        f.add("12000", "Montant des dividendes (déterminés et autres que déterminés)", eligible + other,
              "dividendes réels majorés de 38 % (déterminés) et de 15 % (autres)",
              params=("federal.dividends.eligible_gross_up", "federal.dividends.other_gross_up")),
        f.add("12100", "Intérêts et autres revenus de placements", tp.interest_income),
        f.add("12700", "Gains en capital imposables", annex_3.amount("19900") if annex_3 is not None else 0.0,
              "annexe 3, ligne 19900 si applicable", refs=("5000-S3:19900",) if annex_3 is not None else ()),
        f.add("12900", "Revenus d'un régime enregistré d'épargne-retraite (REER)", tp.rrsp_income + rrsp_annuities),
        f.add("13000", "Autres revenus", other_rrif, "FERR avant 65 ans, hors revenus admissibles de survivant",
              params=("federal.pension_amount.minimum_age_for_rrif",)),
    ]
    f.add("12010", "Montant des dividendes (autres que déterminés)", other, "inclus à la ligne 12000",
          params=("federal.dividends.other_gross_up",))
    income_refs = ("T1:10100", "T1:11300", "T1:11400", "T1:11500", "T1:12000", "T1:12100",
                   "T1:12700", "T1:12900", "T1:13000")
    split = forms.get("T1032")
    if split is not None and split_recipient:
        income.append(f.add("11600", "Choix du montant de pension fractionné", split.amount("22"), refs=("T1032:22",)))
        income_refs += ("T1:11600",)
    benefits = tp.benefits
    if benefits is not None:
        insured = benefits.ei_regular + benefits.ei_special + benefits.ei_maternity_parental + benefits.qpip
        if insured:
            income.append(f.add("11900", "Prestations d'assurance-emploi et autres prestations", insured,
                                "prestations AE imposables et RQAP, hors prestations exonérées"))
            f.add("11905", "Prestations de maternité et parentales de l'AE et prestations du RPAP",
                  benefits.ei_maternity_parental + benefits.qpip, "déjà incluses à la ligne 11900")
            income_refs += ("T1:11900",)
        if benefits.workers_compensation or benefits.social_assistance or benefits.federal_supplements:
            compensation = f.add("14400", "Indemnités pour accidents du travail", benefits.workers_compensation)
            assistance = f.add("14500", "Prestations d'assistance sociale", benefits.social_assistance,
                               "montant attribué à ce déclarant selon les règles fédérales du ménage")
            supplements = f.add("14600", "Versement net des suppléments fédéraux", benefits.federal_supplements)
            income.append(f.add("14700", "Total des autres paiements", compensation + assistance + supplements,
                                refs=("T1:14400", "T1:14500", "T1:14600")))
            income_refs += ("T1:14700",)
    total = f.add("15000", "Revenu total", sum(income), refs=income_refs)

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
    deduction_refs = ("T1:20800", "T1:22215")
    if split is not None and not split_recipient:
        deductions += f.add("21000", "Déduction pour le choix du montant de pension fractionné", split.amount("22"),
                            refs=("T1032:22",))
        deduction_refs += ("T1:21000",)
    if tp.deductions is not None:
        deductions += f.add("20700", "Déduction pour régimes de pension agréés (RPA)", tp.deductions.rpp)
        deductions += f.add("21200", "Cotisations annuelles syndicales, professionnelles et semblables",
                            tp.deductions.union_dues_federal)
        deduction_refs += ("T1:20700", "T1:21200")
    if benefits is not None:
        repaid = benefits.ei_repaid + benefits.qpip_repaid + benefits.oas_overpayment_recovered
        if repaid:
            deductions += f.add("23200", "Autres déductions", repaid,
                                "trop-perçus AE, RQAP et PSV remboursés, déductibles cette année")
            deduction_refs += ("T1:23200",)
    before = f.add("23400", "Revenu net avant rajustements", total - deductions,
                   refs=("T1:15000",) + deduction_refs)
    worksheet = None
    if pension_income or eligible_annuity or tp.oas_pension or benefits is not None:
        worksheet = federal_schedules.worksheet(tp, params, f, eligible_annuity)
    if worksheet is not None:
        forms[worksheet.code] = worksheet
    has_recovery = worksheet is not None and "23500-21" in worksheet.lines
    repayment = f.add("23500", "Remboursement des prestations de programmes sociaux",
                      worksheet.amount("23500-21") if has_recovery else 0.0,
                      "grille 23500 : récupération AE, puis PSV et suppléments fédéraux",
                      refs=("5000-D1:23500-21",) if has_recovery else ("T1:23400", "T1:11300"),
                      params=("federal.oas_recovery.threshold", "federal.oas_recovery.rate"))
    net = f.add("23600", "Revenu net", max(0.0, before - repayment), "minimum zéro",
                refs=("T1:23400", "T1:23500"))
    other_deduction = 0.0
    taxable_refs = ("T1:23600",)
    if "14700" in f.lines:
        ei_recovery = worksheet.amount("23500-7") if has_recovery else 0.0
        supplements_repaid = max(0.0, repayment - tp.oas_pension - ei_recovery)
        other_deduction = f.add("25000", "Déductions pour autres paiements",
            f.amount("14400") + f.amount("14500") + max(0.0, f.amount("14600") - supplements_repaid),
            "ligne 14700 moins les suppléments récupérés au-delà de la PSV et du remboursement AE; "
            "tableau officiel ARC de la ligne 25000",
            refs=("T1:14700", "T1:14600", "T1:23500", "T1:11300")
                 + (("5000-D1:23500-7",) if has_recovery else ())
                 + (("5000-D1:25000-9",) if f.amount("14600") else ()))
        taxable_refs += ("T1:25000",)
    taxable = f.add("26000", "Revenu imposable", max(0.0, net - other_deduction), refs=taxable_refs)

    return f


def federal_personal_credits(tp: Taxpayer, params: dict, qpp: QppContributions, *,
                             forms: dict[str, Form], coordinated: bool = False,
                             split_recipient: bool = False) -> Form:
    """Remplit les droits personnels nécessaires avant les transferts entre conjoints."""
    fed, cot = params["federal"], params["cotisations"]
    f = forms["T1"]
    net = f.amount("23600")
    annex_8 = forms.get("5005-S8")
    worksheet = forms.get("5000-D1")
    pension = worksheet.amount("31400-8") if worksheet is not None else 0.0
    pension_ref = "5000-D1:31400-8" if pension else "T1:11500"
    if "T1032" in forms:
        number = "34" if split_recipient else "31"
        pension = forms["T1032"].amount(number)
        pension_ref = f"T1032:{number}"
    # Étape 5, partie B — Crédits d'impôt non remboursables
    f.add("30000", "Montant personnel de base", rules.federal_basic_personal_amount(net, fed["basic_personal_amount"]),
          "bonification réduite linéairement entre les 4e et 5e paliers, selon la ligne 23600",
          refs=("T1:23600",),
          params=(
              "federal.basic_personal_amount.maximum",
              "federal.basic_personal_amount.minimum",
              "federal.basic_personal_amount.phase_out_start",
              "federal.basic_personal_amount.phase_out_end",
          ))
    f.add("30100", "Montant en raison de l'âge", rules.federal_age_amount(tp.age, net, fed["age_amount"]),
          "65 ans et plus, moins 15 % de la ligne 23600 au-delà du seuil",
          refs=("T1:23600",),
          params=(
              "federal.age_amount.amount",
              "federal.age_amount.threshold",
              "federal.age_amount.reduction_rate",
              "federal.age_amount.minimum_age",
          ))
    f.add("30800", "Cotisations de base au RPC ou au RRQ pour les revenus d'emploi",
          annex_8.amount("P2-35") if annex_8 is not None else qpp.base,
          "annexe 8, partie 2, ligne 35 si applicable",
          refs=("5005-S8:P2-35",) if annex_8 is not None else (),
          params=(
              "cotisations.qpp.basic_exemption",
              "cotisations.qpp.maximum_pensionable_earnings",
              "cotisations.qpp.base_rate",
          ))
    f.add("31200", "Cotisations de l'employé à l'assurance-emploi",
          rules.insurable_premium(tp.employment_income, cot["employment_insurance"]), "taux du Québec",
          refs=("T1:10100",),
          params=(
              "cotisations.employment_insurance.maximum_insurable_earnings",
              "cotisations.employment_insurance.rate",
          ))
    f.add("31205", "Cotisations au régime provincial d'assurance parentale (RPAP)",
          rules.insurable_premium(tp.employment_income, cot["qpip"]),
          refs=("T1:10100",),
          params=("cotisations.qpip.maximum_insurable_earnings", "cotisations.qpip.rate"))
    f.add("31260", "Montant canadien pour emploi",
          min(fed["canada_employment_amount"]["maximum"], tp.employment_income),
          refs=("T1:10100",),
          params=("federal.canada_employment_amount.maximum",))
    f.add("31400", "Montant pour revenu de pension", min(fed["pension_amount"]["maximum"], pension),
          "T1032, étape 4" if "T1032" in forms else "grille 31400; PSV, RRQ et retraits ordinaires REER exclus",
          refs=(pension_ref,),
          params=("federal.pension_amount.maximum",))
    if coordinated:
        codes = ("30800", "31200", "31205", "31260")
        f.add("100", "Total des lignes 87 à 99", sum(f.amount(n) for n in codes),
              refs=tuple(f"T1:{n}" for n in codes))
    f.add("40400", "Impôt fédéral sur le revenu imposable", rules.bracket_tax(f.amount("26000"), fed["brackets"]),
          "partie A, ligne 77; aucun impôt sur le revenu fractionné", refs=("T1:26000",),
          params=("federal.brackets.thresholds", "federal.brackets.rates"))
    return f


def federal_tax(tp: Taxpayer, params: dict, *, forms: dict[str, Form]) -> Form:
    """Applique les crédits personnels et transférés, puis l’impôt minimum et l’abattement."""
    fed = params["federal"]
    f = forms["T1"]
    eligible, other = rules.grossed_up_dividends(tp.eligible_dividends, tp.other_dividends, fed["dividends"])
    repayment = f.amount("23500")
    codes = ("30000", "30100", "30800", "31200", "31205", "31260", "31400")
    refs = ("T1:30000", "T1:30100", "T1:30800", "T1:31200", "T1:31205", "T1:31260", "T1:31400")
    for number in ("30300", "30425", "32600"):
        if number in f.lines:
            codes += (number,)
            refs += (f"T1:{number}",)
    total_amounts = f.add("33500", "Total des montants", sum(f.lines[n].amount for n in codes), refs=refs)
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
    tax = f.amount("40400")
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
