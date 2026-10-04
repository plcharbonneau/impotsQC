# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclaration de revenus du Québec TP-1, ligne par ligne, avec les annexes B, F et K.

Numéros et libellés : TP-1.D (2025-12) et ses annexes; la version 2026 n'est pas publiée au
2026-10-04. Sont nuls hors portée : crédits transférés entre conjoints (431), report de l'impôt
minimum d'une année passée. L'impôt minimum de remplacement (annexe E, partie B; TP-776.42) suit
les paramètres officiels connus, le formulaire TP-776.42 n'ayant pas pu être lu.
"""

from __future__ import annotations

from . import rules
from .model import Form, Taxpayer
from .rules import QppContributions


def quebec_return(tp: Taxpayer, params: dict, qpp: QppContributions, oas_repayment: float) -> Form:
    """Remplit le TP-1 de `tp`. `oas_repayment` : ligne 23500 du T1 (déduite à la ligne 250)."""
    qc, cot = params["quebec"], params["cotisations"]
    f = Form("TP-1")

    # Cotisations retenues sur la paie (relevé 1)
    f.add("97", "Cotisation au RQAP", rules.insurable_premium(tp.employment_income, cot["qpip"]), "relevé 1, case H")
    f.add("98", "Cotisation au RRQ", qpp.base + qpp.first_additional, "relevé 1, case B.A : base et premier supplément")
    f.add("98.2", "Cotisation supplémentaire au RRQ", qpp.second_additional, "relevé 1, case B.B : deuxième supplément")

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
        f.add("128", "Montant imposable des dividendes", eligible + other, "lignes 166 et 167 majorées"),
        f.add("130", "Intérêts et autres revenus de placement", tp.interest_income),
        f.add("139", "Gains en capital imposables", tp.capital_gains * incl, f"annexe G : gain × {incl:g}"),
    ]
    total = f.add("199", "Revenu total", sum(income))

    # Revenu net et revenu imposable
    w = qc["workers_deduction"]
    deductions = [
        f.add("201", "Déduction pour travailleur", min(w["maximum"], w["rate"] * tp.employment_income),
              "6 % du revenu de travail, maximum de l'année"),
        f.add("214", "Déduction pour REER ou RPAC/RVER", tp.rrsp_deduction),
        f.add("248", "Déduction pour cotisation au RRQ, au RPC ou au RQAP", qpp.enhanced,
              "cotisations supplémentaires au RRQ (annexe U, partie B)"),
        f.add("250", "Autres déductions", oas_repayment,
              "point 03 : remboursement de prestations (ligne 23500 fédérale)"),
    ]
    total_deductions = f.add("254", "Total des déductions", sum(deductions))
    f.add("256", "Montant de la ligne 199 moins celui de la ligne 254", total - total_deductions)
    net = f.add("275", "Revenu net", max(0.0, total - total_deductions))
    taxable = f.add("299", "Revenu imposable", net, "aucune déduction des lignes 287 à 297 dans la portée")

    # Crédits d'impôt non remboursables
    base = f.add("350", "Montant personnel de base", qc["basic_personal_amount"]["amount"])
    retirement = tp.rrsp_income + tp.rrif_income
    schedule_b = f.add("361", "Montant accordé en raison de l'âge ou pour personne vivant seule ou pour revenus de retraite",
                       rules.schedule_b_amount(age=tp.age, lives_alone=tp.lives_alone, retirement_income=retirement,
                                               family_income=net, table=qc["schedule_b"]),
                       "annexe B : revenus de retraite = lignes 122 et 123 × 1,25 (maximum), moins 18,75 % "
                       "du revenu familial au-delà du seuil")
    amounts = f.add("377", "Total des montants (lignes 359 à 376)", base + schedule_b)
    credits = f.add("377.1", "Montant de la ligne 377 multiplié par 14 %", amounts * qc["credits"]["rate"])
    tax = rules.bracket_tax(taxable, qc["brackets"])
    career = f.add("391", "Crédit d'impôt pour prolongation de carrière",
                   min(rules.career_extension_credit(age=tp.age, work_income=tp.employment_income, net_income=net,
                                                     table=qc["career_extension"]),
                       max(0.0, tax - credits)),
                   "TP-752.PC : 14 % du revenu de travail au-delà de l'exclusion (plafonné), moins 7 % du "
                   "revenu net au-delà du seuil; 65 ans et plus; limité à l'impôt qui reste après les autres crédits")
    credits = f.add("399", "Crédits d'impôt non remboursables", credits + career)

    # Impôt
    f.add("401", "Impôt sur le revenu imposable", tax)
    f.add("406", "Crédits d'impôt non remboursables (ligne 399)", credits)
    after = f.add("413", "Montant de la ligne 401 moins celui de la ligne 406", max(0.0, tax - credits))
    dividend_credit = f.add("415", "Crédit d'impôt pour dividendes",
                            sum(rules.dividend_tax_credit(eligible, other, qc["dividends"])),
                            "pourcentage du montant majoré")
    f.add("425", "Total des lignes 414 à 424", dividend_credit)
    regular = f.add("430", "Montant de la ligne 413 moins celui de la ligne 425", after - dividend_credit)

    # Annexe E, partie B, et TP-776.42 — impôt minimum de remplacement
    amt = rules.minimum_tax(taxable_income=taxable, capital_gains=tp.capital_gains, capital_gains_inclusion=incl,
                            addback_deductions=qpp.enhanced,
                            dividend_gross_up=(eligible - tp.eligible_dividends) + (other - tp.other_dividends),
                            credits=credits, table=qc["minimum_tax"])
    if amt.net_adjusted_taxable_income > 0:
        f.add("TP-776.42:rajuste", "Revenu imposable rajusté", amt.adjusted_taxable_income,
              "revenu imposable + gains en capital à 100 % + 50 % de la ligne 248 − majoration des dividendes")
        f.add("E:15", "Impôt minimum de remplacement, selon le formulaire TP-776.42", amt.minimum_amount,
              "19 % au-delà de l'exemption − 50 % des crédits non remboursables (ligne 399)")
    quebec_tax = f.add("432", "Impôt du Québec", max(0.0, regular, amt.minimum_amount),
                       "annexe E, partie B : le plus élevé de l'impôt ordinaire et de l'impôt minimum")

    # Cotisations
    fss_base = total - tp.employment_income - tp.oas_pension - (eligible + other - tp.eligible_dividends - tp.other_dividends)
    fss = f.add("446", "Cotisation au Fonds des services de santé (FSS)",
                rules.health_services_fund(fss_base, qc["health_services_fund"]),
                "annexe F : revenu total moins emploi, PSV et majoration des dividendes")
    drug = f.add("447", "Cotisation au régime d'assurance médicaments du Québec",
                 rules.drug_insurance_premium(net, qc["drug_insurance"]),
                 "annexe K : particulier sans conjoint, assuré toute l'année")
    f.add("450", "Impôt et cotisations", quebec_tax + fss + drug)
    return f
