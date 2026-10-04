# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Annexes du Québec, avec la numérotation des documents officiels 2025.

Seules les parties utilisées par le moteur sont remplies. Les situations hors portée (conjoint,
reports, autres déductions) restent hors portée : l'extraction ne corrige pas les règles de 0.2.
Une fonction rend None avant de construire un formulaire qui ne s'applique pas.
"""

from __future__ import annotations

from . import rules
from .model import Form, Taxpayer


def schedule_b(tp: Taxpayer, params: dict, quebec: Form) -> Form | None:
    """Annexe B, parties A et B et grille de retraite; particulier sans conjoint."""
    t = params["quebec"]["schedule_b"]
    retirement = quebec.amount("122")
    if not (tp.lives_alone or tp.age >= t["minimum_age"] or retirement > 0):
        return None
    f = Form.from_parameters("TP-1.D.B", params)
    net = f.add("10", "Revenu net", quebec.amount("275"),
                refs=("TP-1:275",))
    f.add("14", "Revenu familial", net, "sans conjoint",
          refs=("TP-1.D.B:10",))
    f.add("15", "Revenu familial", net,
          refs=("TP-1.D.B:14",))
    threshold = f.add("16", "Seuil de réduction", t["reduction_threshold"],
                      params=("quebec.schedule_b.reduction_threshold",))
    excess = f.add("18", "Revenu familial excédant le seuil", max(0.0, net - threshold),
                   refs=("TP-1.D.B:15", "TP-1.D.B:16"))
    alone = f.add("20", "Montant pour personne vivant seule", t["living_alone"] if tp.lives_alone else 0.0,
                  params=("quebec.schedule_b.living_alone",))
    age = f.add("22", "Montant accordé en raison de l'âge", t["age"] if tp.age >= t["minimum_age"] else 0.0,
                params=("quebec.schedule_b.age", "quebec.schedule_b.minimum_age"))
    pension = 0.0
    if retirement > 0:
        f.add("1", "Revenus de retraite", retirement, "grille de calcul, lignes 122 et 123 dans la portée",
              refs=("TP-1:122",))
        f.add("8", "Revenus de retraite admissibles", retirement, "aucun transfert ni déduction visée",
              refs=("TP-1.D.B:1",))
        pension = f.add("9", "Montant pour revenus de retraite",
                        min(t["retirement_income_factor"] * retirement, t["retirement_income_maximum"]),
                        "grille : ligne 8 × facteur, plafonné",
                        refs=("TP-1.D.B:8",),
                        params=(
                            "quebec.schedule_b.retirement_income_factor",
                            "quebec.schedule_b.retirement_income_maximum",
                        ))
    f.add("27", "Montant pour revenus de retraite", pension,
          refs=("TP-1.D.B:9",) if retirement > 0 else ())
    f.add("30", "Total des montants", alone + age + pension,
          refs=("TP-1.D.B:20", "TP-1.D.B:22", "TP-1.D.B:27"))
    f.add("31", "Réduction selon le revenu familial", t["reduction_rate"] * excess,
          refs=("TP-1.D.B:18",),
          params=("quebec.schedule_b.reduction_rate",))
    amount = rules.schedule_b_amount(age=tp.age, lives_alone=tp.lives_alone, retirement_income=retirement,
                                     family_income=net, table=t)
    f.add("32", "Montant auquel vous avez droit", amount, "ligne 30 − ligne 31, minimum zéro",
          refs=("TP-1.D.B:30", "TP-1.D.B:31"))
    f.add("34", "Montant accordé en raison de l'âge ou pour personne vivant seule ou pour revenus de retraite",
          amount, "sans montant demandé par un conjoint",
          refs=("TP-1.D.B:32",))
    return f


def schedule_f(params: dict, quebec: Form) -> Form | None:
    """Annexe F, revenu assujetti et colonne du barème applicable au contribuable."""
    t = params["quebec"]["health_services_fund"]
    total, employment, oas = quebec.amount("199"), quebec.amount("101"), quebec.amount("114")
    dividends = quebec.amount("128")
    gross_up = dividends - quebec.amount("166") - quebec.amount("167")
    base = total - employment - oas - gross_up
    if base <= t["first_threshold"]:
        return None
    f = Form.from_parameters("TP-1.D.F", params)
    f.add("10", "Revenu total", total,
          refs=("TP-1:199",))
    f.add("12", "Revenus d'emploi", employment,
          refs=("TP-1:101",))
    f.add("16", "Revenus d'emploi corrigés", employment, "aucune correction",
          refs=("TP-1.D.F:12",))
    f.add("18", "Revenu moins revenus d'emploi", total - employment,
          refs=("TP-1.D.F:10", "TP-1.D.F:16"))
    f.add("22", "Pension de sécurité de la vieillesse", oas,
          refs=("TP-1:114",))
    f.add("23", "Montant imposable des dividendes", dividends,
          refs=("TP-1:128",))
    f.add("24", "Montant réel des dividendes", quebec.amount("166") + quebec.amount("167"),
          refs=("TP-1:166", "TP-1:167"))
    f.add("25", "Majoration des dividendes", gross_up,
          refs=("TP-1.D.F:23", "TP-1.D.F:24"))
    f.add("34", "Total des revenus exclus", oas + gross_up,
          refs=("TP-1.D.F:22", "TP-1.D.F:25"))
    f.add("36", "Revenu", base,
          refs=("TP-1.D.F:18", "TP-1.D.F:34"))
    f.add("70", "Revenu assujetti à la cotisation", base, "aucune déduction visée dans la portée",
          refs=("TP-1.D.F:36",))
    f.add("76", "Revenu assujetti à la cotisation", base,
          refs=("TP-1.D.F:70",))
    upper = base > t["second_threshold"]
    threshold = f.add("77", "Seuil de la colonne applicable", t["second_threshold"] if upper else t["first_threshold"],
                      params=(
                          "quebec.health_services_fund.first_threshold",
                          "quebec.health_services_fund.second_threshold",
                      ))
    excess = f.add("78", "Revenu excédant le seuil", max(0.0, base - threshold),
                   refs=("TP-1.D.F:76", "TP-1.D.F:77"))
    f.add("80", "Cotisation sur le revenu excédentaire", t["rate"] * excess,
          refs=("TP-1.D.F:78",),
          params=("quebec.health_services_fund.rate",))
    f.add("81", "Cotisation de base de la colonne applicable", t["first_maximum"] if upper else 0.0,
          params=("quebec.health_services_fund.first_maximum",))
    f.add("82", "Cotisation au FSS", rules.health_services_fund(base, t), "lignes 80 + 81, maximum de la colonne",
          refs=("TP-1.D.F:80", "TP-1.D.F:81"),
          params=("quebec.health_services_fund.first_maximum", "quebec.health_services_fund.maximum"))
    return f


def schedule_k(params: dict, quebec: Form) -> Form | None:
    """Annexe K, particulier sans conjoint, assuré toute l'année comme dans l'API 0.2."""
    t = params["quebec"]["drug_insurance"]
    net = quebec.amount("275")
    if net <= t["exemption_single"]:
        return None
    f = Form.from_parameters("TP-1.D.K", params)
    f.add("36", "Revenu net", net,
          refs=("TP-1:275",))
    f.add("40", "Revenu familial", net, "sans conjoint",
          refs=("TP-1.D.K:36",))
    exemption = f.add("41", "Exemption", t["exemption_single"],
                      params=("quebec.drug_insurance.exemption_single",))
    f.add("46", "Exemption totale", exemption, "sans conjoint ni enfant à charge",
          refs=("TP-1.D.K:41",))
    x = f.add("48", "Revenu servant à calculer la cotisation", net - exemption,
              refs=("TP-1.D.K:40", "TP-1.D.K:46"))
    f.add("62", "Nombre de mois exemptés", 0.0, "hypothèse héritée : assuré au régime public toute l'année")
    width = t["first_bracket_width"]
    raw = x * t["first_rate_single"] if x <= width else width * t["first_rate_single"] + (x - width) * t["second_rate_single"]
    if raw >= t["rate_cap"]:
        premium = f.add("84", "Cotisation de la colonne applicable", t["rate_cap"], "plafond atteint",
                        refs=("TP-1.D.K:48",),
                        params=(
                            "quebec.drug_insurance.rate_cap",
                            "quebec.drug_insurance.first_bracket_width",
                            "quebec.drug_insurance.first_rate_single",
                            "quebec.drug_insurance.second_rate_single",
                        ))
    else:
        f.add("77", "Revenu servant à calculer la cotisation", x,
              refs=("TP-1.D.K:48",))
        upper = x > width
        threshold = f.add("78", "Seuil de la colonne applicable", width if upper else 0.0,
                          params=("quebec.drug_insurance.first_bracket_width",))
        excess = f.add("79", "Revenu excédant le seuil", x - threshold,
                       refs=("TP-1.D.K:77", "TP-1.D.K:78"))
        rate = f.add("80", "Taux de la colonne applicable", t["second_rate_single"] if upper else t["first_rate_single"],
                     "taux exprimé comme fraction",
                     params=("quebec.drug_insurance.first_rate_single", "quebec.drug_insurance.second_rate_single"))
        f.add("81", "Cotisation sur le revenu excédentaire", excess * rate,
              refs=("TP-1.D.K:79", "TP-1.D.K:80"))
        f.add("82", "Cotisation de base de la colonne applicable", width * t["first_rate_single"] if upper else 0.0,
              params=("quebec.drug_insurance.first_bracket_width", "quebec.drug_insurance.first_rate_single"))
        f.add("83", "Cotisation selon le revenu", raw, "lignes 81 + 82, plafond non atteint",
              refs=("TP-1.D.K:81", "TP-1.D.K:82"),
              params=("quebec.drug_insurance.rate_cap",))
        premium = f.add("84", "Cotisation de la colonne applicable", raw,
                        refs=("TP-1.D.K:83",))
    f.add("85", "Réduction pour les mois exemptés", 0.0, "aucun mois exempté",
          refs=("TP-1.D.K:84", "TP-1.D.K:62"))
    f.add("86", "Cotisation pour les mois assurés", premium,
          refs=("TP-1.D.K:84", "TP-1.D.K:85"))
    maximum = f.add("87", "Cotisation maximale pour l'année", t["annual_maximum"],
                    params=("quebec.drug_insurance.annual_maximum",))
    f.add("88", "Réduction du maximum pour les mois exemptés", 0.0, "aucun mois exempté",
          refs=("TP-1.D.K:62",))
    f.add("89", "Maximum pour les mois assurés", maximum,
          refs=("TP-1.D.K:87", "TP-1.D.K:88"))
    amount = f.add("90", "Cotisation personnelle", rules.drug_insurance_premium(net, t), "minimum des lignes 86 et 89",
                   refs=("TP-1.D.K:86", "TP-1.D.K:89"))
    f.add("98", "Cotisation au régime d'assurance médicaments du Québec", amount, "sans cotisation d'un conjoint",
          refs=("TP-1.D.K:90",))
    return f


def career_extension(tp: Taxpayer, params: dict, quebec: Form) -> Form | None:
    """TP-752.PC : revenu de travail, réduction et limite de l'impôt restant, ligne finale 50."""
    t = params["quebec"]["career_extension"]
    if tp.age < t["minimum_age"] or tp.employment_income <= 0:
        return None
    f = Form.from_parameters("TP-752.PC", params)
    work = f.add("10", "Revenu de travail admissible", tp.employment_income,
                 refs=("TP-1:101",),
                 params=("quebec.career_extension.minimum_age",))
    f.add("12", "Revenu de travail après exclusions", work, "aucune exclusion visée",
          refs=("TP-752.PC:10",))
    f.add("14", "Revenu de travail de l'année", work, "aucun montant rétroactif",
          refs=("TP-752.PC:12",))
    excluded = f.add("15", "Montant exclu", t["excluded_income"],
                     params=("quebec.career_extension.excluded_income",))
    eligible = f.add("16", "Revenu de travail donnant droit au crédit", min(max(0.0, work - excluded), t["maximum_eligible_income"]),
                     "ligne 14 − ligne 15, entre zéro et le maximum",
                     refs=("TP-752.PC:14", "TP-752.PC:15"),
                     params=("quebec.career_extension.maximum_eligible_income",))
    f.add("35", "Crédit avant réduction", eligible * t["credit_rate"],
          refs=("TP-752.PC:16",),
          params=("quebec.career_extension.credit_rate",))
    net = f.add("36", "Revenu net", quebec.amount("275"),
                refs=("TP-1:275",))
    threshold = f.add("37", "Seuil de réduction", t["reduction_threshold"],
                      params=("quebec.career_extension.reduction_threshold",))
    excess = f.add("38", "Revenu net excédant le seuil", max(0.0, net - threshold),
                   refs=("TP-752.PC:36", "TP-752.PC:37"))
    f.add("39", "Réduction du crédit", t["reduction_rate"] * excess,
          refs=("TP-752.PC:38",),
          params=("quebec.career_extension.reduction_rate",))
    credit = f.add("40", "Crédit après réduction", rules.career_extension_credit(age=tp.age, work_income=work, net_income=net, table=t),
                   "ligne 35 − ligne 39, minimum zéro",
                   refs=("TP-752.PC:35", "TP-752.PC:39"))
    tax = f.add("47", "Impôt sur le revenu imposable", quebec.amount("401"),
                refs=("TP-1:401",))
    credits = f.add("48", "Crédits sur les montants des lignes 359 à 367", quebec.amount("377.1"),
                    "dans la portée : base et annexe B seulement",
                    refs=("TP-1:377.1",))
    remaining = f.add("49", "Impôt restant", max(0.0, tax - credits),
                      refs=("TP-752.PC:47", "TP-752.PC:48"))
    f.add("50", "Crédit d'impôt pour prolongation de carrière", min(credit, remaining),
          refs=("TP-752.PC:40", "TP-752.PC:49"))
    return f


def minimum_tax(tp: Taxpayer, params: dict, quebec: Form, dividend_gross_up: float) -> Form | None:
    """TP-776.42 : revenu modifié, exemption et déduction de base, selon la portée du moteur 0.2."""
    t = params["quebec"]["minimum_tax"]
    inclusion = params["federal"]["capital_gains"]["inclusion_rate"]
    taxable, enhanced = quebec.amount("299"), quebec.amount("248")
    amt = rules.minimum_tax(taxable_income=taxable, capital_gains=tp.capital_gains, capital_gains_inclusion=inclusion,
                            addback_deductions=enhanced, dividend_gross_up=dividend_gross_up,
                            credits=quebec.amount("399"), table=t)
    if amt.net_adjusted_taxable_income <= 0:
        return None
    f = Form.from_parameters("TP-776.42", params)
    f.add("1", "Revenu imposable", taxable, "base du moteur 0.2, après plancher à zéro",
          refs=("TP-1:299",))
    gains = f.add("10", "Ajout pour les gains en capital", tp.capital_gains * (t["capital_gains_inclusion"] - inclusion),
                  "gain réalisé × différence des taux d'inclusion",
                  refs=("TP-1:139",),
                  params=("quebec.minimum_tax.capital_gains_inclusion", "federal.capital_gains.inclusion_rate"))
    added = t["deduction_addback_rate"] * enhanced
    if enhanced > 0:
        f.add("157.5", "Déduction pour cotisation au RRQ, au RPC ou au RQAP", enhanced,
              refs=("TP-1:248",))
        f.add("158", "Déductions rajoutées", added,
              "portée héritée : cotisations bonifiées seulement; déduction pour travailleur non rajoutée",
              refs=("TP-776.42:157.5",),
              params=("quebec.minimum_tax.deduction_addback_rate",))
        f.add("160", "Autres ajouts au revenu imposable", added,
              refs=("TP-776.42:158",))
    f.add("17", "Autres ajouts au revenu imposable", added,
          refs=("TP-776.42:160",) if enhanced > 0 else ("TP-1:248",),
          params=("quebec.minimum_tax.deduction_addback_rate",))
    f.add("18", "Revenu imposable après ajouts", taxable + gains + added,
          refs=("TP-776.42:1", "TP-776.42:10", "TP-776.42:17"))
    if dividend_gross_up > 0:
        f.add("163.2", "Majoration des dividendes", dividend_gross_up, "montant imposable moins montants réels",
              refs=("TP-1:128", "TP-1:166", "TP-1:167"))
        f.add("172", "Réduction du revenu imposable", dividend_gross_up,
              refs=("TP-776.42:163.2",))
    f.add("19", "Réduction du revenu imposable", dividend_gross_up,
          refs=("TP-776.42:172",) if dividend_gross_up > 0 else ("TP-1:128", "TP-1:166", "TP-1:167"))
    f.add("22", "Revenu imposable modifié", amt.adjusted_taxable_income, "ligne 18 − ligne 19 dans la portée",
          refs=("TP-776.42:18", "TP-776.42:19"))
    f.add("23", "Exemption de base", t["exemption"],
          params=("quebec.minimum_tax.exemption",))
    f.add("24", "Revenu modifié au-delà de l'exemption", amt.net_adjusted_taxable_income,
          "ligne 22 − ligne 23, minimum zéro",
          refs=("TP-776.42:22", "TP-776.42:23"))
    f.add("25", "Taux de l'IMR", t["rate"], "taux exprimé comme fraction",
          params=("quebec.minimum_tax.rate",))
    f.add("26", "Impôt minimum avant déduction", amt.net_adjusted_taxable_income * t["rate"],
          refs=("TP-776.42:24", "TP-776.42:25"))
    credits = f.add("250", "Crédits d'impôt non remboursables", quebec.amount("399"),
                    refs=("TP-1:399",))
    deduction = f.add("254", "Crédits admis aux fins de l'IMR", credits * t["credit_fraction"], "aucun don dans la portée",
                      refs=("TP-776.42:250",),
                      params=("quebec.minimum_tax.credit_fraction",))
    f.add("258", "Déduction d'impôt minimum de base", deduction, "aucun crédit transféré",
          refs=("TP-776.42:254",))
    f.add("27", "Déduction d'impôt minimum de base", deduction,
          refs=("TP-776.42:258",))
    f.add("30", "Impôt minimum après déduction", amt.minimum_amount, "ligne 26 − ligne 27, minimum zéro",
          refs=("TP-776.42:26", "TP-776.42:27"))
    f.add("32", "Impôt minimum applicable", amt.minimum_amount, "100 % au Québec",
          refs=("TP-776.42:30",))
    f.add("34", "Impôt minimum de remplacement", amt.minimum_amount, "aucun crédit pour impôt étranger",
          refs=("TP-776.42:32",))
    return f


def schedule_e(params: dict, quebec: Form, minimum: Form) -> Form:
    """Annexe E, partie B : compare l'impôt ordinaire au TP-776.42, sans report d'années passées."""
    f = Form.from_parameters("TP-1.D.E", params)
    ordinary = f.add("10", "Montant de la ligne 430 de votre déclaration", quebec.amount("430"),
                     refs=("TP-1:430",))
    f.add("12", "Impôt après crédits transférés", max(0.0, ordinary), "sans conjoint",
          refs=("TP-1.D.E:10",))
    f.add("14", "Impôt après report de l'IMR", max(0.0, ordinary), "report non modélisé",
          refs=("TP-1.D.E:12",))
    amt = f.add("15", "Impôt minimum de remplacement", minimum.amount("34"),
                refs=("TP-776.42:34",))
    tax = f.add("16", "Impôt après redressement", max(0.0, ordinary, amt), "maximum des lignes 14 et 15",
                refs=("TP-1.D.E:14", "TP-1.D.E:15"))
    f.add("18", "Impôt du Québec", tax, "aucune déduction relative aux opérations forestières",
          refs=("TP-1.D.E:16",))
    return f
