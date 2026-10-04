# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclaration de revenus du Québec TP-1, ligne par ligne, avec les annexes B, F et K.

Numéros et libellés : TP-1.D (2025-12) et ses annexes; la version 2026 n'est pas publiée au
2026-10-04. Sont nuls hors portée : crédits transférés entre conjoints (431), report de l'impôt
minimum d'une année passée. L'impôt minimum de remplacement (annexe E, partie B; TP-776.42) suit
les règles du moteur 0.2, désormais exposées dans des formulaires distincts.
"""

from __future__ import annotations

from . import quebec_schedules, rules
from .model import Form, Taxpayer
from .rules import QppContributions


def quebec_return(tp: Taxpayer, params: dict, qpp: QppContributions, oas_repayment: float, *, forms: dict[str, Form]) -> Form:
    """Remplit le TP-1 de `tp`. `oas_repayment` : ligne 23500 du T1 (déduite à la ligne 250)."""
    qc, cot = params["quebec"], params["cotisations"]
    f = Form.from_parameters("TP-1", params)
    forms[f.code] = f

    # Cotisations retenues sur la paie (relevé 1)
    f.add("97", "Cotisation au RQAP", rules.insurable_premium(tp.employment_income, cot["qpip"]), "relevé 1, case H",
          refs=("TP-1:101",),
          params=("cotisations.qpip.maximum_insurable_earnings", "cotisations.qpip.rate"))
    f.add("98", "Cotisation au RRQ", qpp.base + qpp.first_additional, "relevé 1, case B.A : base et premier supplément",
          refs=("TP-1:101",),
          params=(
              "cotisations.qpp.basic_exemption",
              "cotisations.qpp.maximum_pensionable_earnings",
              "cotisations.qpp.base_rate",
              "cotisations.qpp.first_additional_rate",
          ))
    f.add("98.2", "Cotisation supplémentaire au RRQ", qpp.second_additional, "relevé 1, case B.B : deuxième supplément",
          refs=("TP-1:101",),
          params=(
              "cotisations.qpp.maximum_pensionable_earnings",
              "cotisations.qpp.additional_maximum_pensionable_earnings",
              "cotisations.qpp.second_additional_rate",
          ))

    # Revenu total
    eligible, other = rules.grossed_up_dividends(tp.eligible_dividends, tp.other_dividends, qc["dividends"])
    incl = params["federal"]["capital_gains"]["inclusion_rate"]
    f.add("166", "Montant réel des dividendes déterminés", tp.eligible_dividends)
    f.add("167", "Montant réel des dividendes ordinaires", tp.other_dividends)
    income = [
        f.add("101", "Revenus d'emploi", tp.employment_income, "relevé 1, case A"),
        f.add("114", "Pension de sécurité de la vieillesse", tp.oas_pension),
        f.add("119", "Prestations du RRQ ou du RPC", tp.qpp_benefits),
        f.add("122", "Prestations d'un régime de retraite, d'un REER, d'un FERR, d'un RPDB ou d'un RPAC/RVER, ou rentes",
              tp.rrsp_income + tp.rrif_income, "retraits REER et FERR"),
        f.add("128", "Montant imposable des dividendes", eligible + other, "lignes 166 et 167 majorées",
              refs=("TP-1:166", "TP-1:167"),
              params=("quebec.dividends.eligible_gross_up", "quebec.dividends.other_gross_up")),
        f.add("130", "Intérêts et autres revenus de placement", tp.interest_income),
        f.add("139", "Gains en capital imposables", tp.capital_gains * incl, f"annexe G : gain × {incl:g}",
              params=("federal.capital_gains.inclusion_rate",)),
    ]
    total = f.add("199", "Revenu total", sum(income),
                  refs=("TP-1:101", "TP-1:114", "TP-1:119", "TP-1:122", "TP-1:128", "TP-1:130", "TP-1:139"))

    # Revenu net et revenu imposable
    w = qc["workers_deduction"]
    deductions = [
        f.add("201", "Déduction pour travailleur", min(w["maximum"], w["rate"] * tp.employment_income),
              "6 % du revenu de travail, maximum de l'année",
              refs=("TP-1:101",),
              params=("quebec.workers_deduction.maximum", "quebec.workers_deduction.rate")),
        f.add("214", "Déduction pour REER ou RPAC/RVER", tp.rrsp_deduction),
        f.add("248", "Déduction pour cotisation au RRQ, au RPC ou au RQAP", qpp.enhanced,
              "cotisations supplémentaires au RRQ (annexe U, partie B)",
              params=(
                  "cotisations.qpp.basic_exemption",
                  "cotisations.qpp.maximum_pensionable_earnings",
                  "cotisations.qpp.additional_maximum_pensionable_earnings",
                  "cotisations.qpp.first_additional_rate",
                  "cotisations.qpp.second_additional_rate",
              )),
        f.add("250", "Autres déductions", oas_repayment,
              "point 03 : remboursement de prestations (ligne 23500 fédérale)",
              refs=("T1:23500",)),
    ]
    total_deductions = f.add("254", "Total des déductions", sum(deductions),
                             refs=("TP-1:201", "TP-1:214", "TP-1:248", "TP-1:250"))
    f.add("256", "Montant de la ligne 199 moins celui de la ligne 254", total - total_deductions,
          refs=("TP-1:199", "TP-1:254"))
    net = f.add("275", "Revenu net", max(0.0, total - total_deductions),
                refs=("TP-1:256",))
    taxable = f.add("299", "Revenu imposable", net, "aucune déduction des lignes 287 à 297 dans la portée",
                    refs=("TP-1:275",))

    # Crédits d'impôt non remboursables
    base = f.add("350", "Montant personnel de base", qc["basic_personal_amount"]["amount"],
                 params=("quebec.basic_personal_amount.amount",))
    annex_b = quebec_schedules.schedule_b(tp, params, f)
    if annex_b is not None:
        forms[annex_b.code] = annex_b
    schedule_b = f.add("361", "Montant accordé en raison de l'âge ou pour personne vivant seule ou pour revenus de retraite",
                       annex_b.amount("34") if annex_b is not None else 0.0, "annexe B, ligne 34 si applicable",
                       refs=("TP-1.D.B:34",) if annex_b is not None else ())
    amounts = f.add("377", "Total des montants (lignes 359 à 376)", base + schedule_b,
                    refs=("TP-1:350", "TP-1:361"))
    credits = f.add("377.1", "Montant de la ligne 377 multiplié par 14 %", amounts * qc["credits"]["rate"],
                    refs=("TP-1:377",),
                    params=("quebec.credits.rate",))
    tax = f.add("401", "Impôt sur le revenu imposable", rules.bracket_tax(taxable, qc["brackets"]),
                refs=("TP-1:299",),
                params=("quebec.brackets.thresholds", "quebec.brackets.rates"))
    annex_pc = quebec_schedules.career_extension(tp, params, f)
    if annex_pc is not None:
        forms[annex_pc.code] = annex_pc
    career = f.add("391", "Crédit d'impôt pour prolongation de carrière",
                   annex_pc.amount("50") if annex_pc is not None else 0.0, "TP-752.PC, ligne 50 si applicable",
                   refs=("TP-752.PC:50",) if annex_pc is not None else ())
    credits = f.add("399", "Crédits d'impôt non remboursables", credits + career,
                    refs=("TP-1:377.1", "TP-1:391"))

    # Impôt
    f.add("406", "Crédits d'impôt non remboursables (ligne 399)", credits,
          refs=("TP-1:399",))
    after = f.add("413", "Montant de la ligne 401 moins celui de la ligne 406", max(0.0, tax - credits),
                  refs=("TP-1:401", "TP-1:406"))
    dividend_credit = f.add("415", "Crédit d'impôt pour dividendes",
                            sum(rules.dividend_tax_credit(eligible, other, qc["dividends"])),
                            "pourcentage du montant majoré",
                            refs=("TP-1:128", "TP-1:166", "TP-1:167"),
                            params=("quebec.dividends.eligible_credit_rate", "quebec.dividends.other_credit_rate"))
    f.add("425", "Total des lignes 414 à 424", dividend_credit,
          refs=("TP-1:415",))
    regular = f.add("430", "Montant de la ligne 413 moins celui de la ligne 425", after - dividend_credit,
                    refs=("TP-1:413", "TP-1:425"))

    # TP-776.42 et annexe E : calculs courants, sans report d'années passées.
    annex_amt = quebec_schedules.minimum_tax(tp, params, f,
        dividend_gross_up=(eligible - tp.eligible_dividends) + (other - tp.other_dividends))
    if annex_amt is not None:
        forms[annex_amt.code] = annex_amt
        annex_e = quebec_schedules.schedule_e(params, f, annex_amt)
        forms[annex_e.code] = annex_e
    quebec_tax = f.add("432", "Impôt du Québec", annex_e.amount("18") if annex_amt is not None else max(0.0, regular),
                       "annexe E, ligne 18 si applicable; sinon impôt ordinaire, minimum zéro",
                       refs=("TP-1.D.E:18",) if annex_amt is not None else ("TP-1:430",))

    annex_f = quebec_schedules.schedule_f(params, f)
    if annex_f is not None:
        forms[annex_f.code] = annex_f
    fss = f.add("446", "Cotisation au Fonds des services de santé (FSS)",
                annex_f.amount("82") if annex_f is not None else 0.0, "annexe F, ligne 82 si applicable",
                refs=("TP-1.D.F:82",) if annex_f is not None else ())
    annex_k = quebec_schedules.schedule_k(params, f)
    if annex_k is not None:
        forms[annex_k.code] = annex_k
    drug = f.add("447", "Cotisation au régime d'assurance médicaments du Québec",
                 annex_k.amount("98") if annex_k is not None else 0.0, "annexe K, ligne 98 si applicable",
                 refs=("TP-1.D.K:98",) if annex_k is not None else ())
    f.add("450", "Impôt et cotisations", quebec_tax + fss + drug,
          refs=("TP-1:432", "TP-1:446", "TP-1:447"))
    return f
