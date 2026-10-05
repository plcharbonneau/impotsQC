# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Annexes du Québec, avec la numérotation des documents officiels 2025.

Seules les parties utilisées par le moteur sont remplies. La RAMQ tient compte du conjoint
fiscal, des enfants admissibles et des mois exemptés déclarés. Les autres limites sont documentées
et signalées dans les avertissements du résultat.
Une fonction rend None avant de construire un formulaire qui ne s'applique pas.
"""

from __future__ import annotations

from . import rules
from .model import Form, Line, Taxpayer


def schedule_b(tp: Taxpayer, params: dict, quebec: Form) -> Form | None:
    """Annexe B : montants personnels d'âge et de retraite, réduction selon le revenu familial.

    Les droits du conjoint et la répartition du montant entre conjoints restent hors portée;
    un avertissement de `compute` signale cette limite pour les couples."""
    t = params["quebec"]["schedule_b"]
    retirement = quebec.amount("122")
    if not (tp.lives_alone or tp.age >= t["minimum_age"] or retirement > 0):
        return None
    f = Form.from_parameters("TP-1.D.B", params)
    net = f.add("10", "Revenu net", quebec.amount("275"),
                refs=("TP-1:275",))
    family_income = net
    family_refs = ("TP-1.D.B:10",)
    if tp.has_spouse:
        family_income += f.add("12", "Revenu net du conjoint", tp.spouse_net_income,
                               "ligne 275 du TP-1 du conjoint, fournie par l'appelant")
        family_refs += ("TP-1.D.B:12",)
    f.add("14", "Revenu familial", family_income, refs=family_refs)
    f.add("15", "Revenu familial", family_income,
          refs=("TP-1.D.B:14",))
    threshold = f.add("16", "Seuil de réduction", t["reduction_threshold"],
                      params=("quebec.schedule_b.reduction_threshold",))
    excess = f.add("18", "Revenu familial excédant le seuil", max(0.0, family_income - threshold),
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
                                     family_income=family_income, table=t)
    f.add("32", "Montant auquel vous avez droit", amount, "ligne 30 − ligne 31, minimum zéro",
          refs=("TP-1.D.B:30", "TP-1.D.B:31"))
    f.add("34", "Montant accordé en raison de l'âge ou pour personne vivant seule ou pour revenus de retraite",
          amount, "sans montant demandé par un conjoint",
          refs=("TP-1.D.B:32",))
    return f


def schedule_f(params: dict, quebec: Form, *, ei_repayment: float = 0.0,
               benefit_repayments: float = 0.0) -> Form | None:
    """Annexe F, revenu assujetti et colonne du barème applicable au contribuable."""
    t = params["quebec"]["health_services_fund"]
    total, employment, oas = quebec.amount("199"), quebec.amount("101"), quebec.amount("114")
    dividends = quebec.amount("128")
    gross_up = dividends - quebec.amount("166") - quebec.amount("167")
    excluded_benefits = quebec.amount("147") + quebec.amount("148")
    income = total - employment - oas - gross_up - excluded_benefits
    base = max(0.0, income - ei_repayment - benefit_repayments)
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
    excluded_refs = ("TP-1.D.F:22", "TP-1.D.F:25")
    for number, target in (("28", "147"), ("29", "148")):
        if target in quebec.lines:
            f.add(number, quebec[target].label, quebec.amount(target), refs=(f"TP-1:{target}",))
            excluded_refs += (f"TP-1.D.F:{number}",)
    f.add("34", "Total des revenus exclus", oas + gross_up + excluded_benefits, refs=excluded_refs)
    f.add("36", "Revenu", income,
          refs=("TP-1.D.F:18", "TP-1.D.F:34"))
    deduction_refs = ()
    if benefit_repayments:
        f.add("41", "Remboursement de sommes reçues en trop", benefit_repayments,
              "partie AE et RQAP de la ligne 246; PSV exclue", refs=("TP-1:246",))
        deduction_refs += ("TP-1.D.F:41",)
    if ei_repayment:
        f.add("44", "Remboursement de prestations d'assurance emploi", ei_repayment,
              "partie AE de la ligne 250; récupération PSV et suppléments exclue",
              refs=("5000-D1:23500-7",))
        deduction_refs += ("TP-1.D.F:44",)
    base_refs = ("TP-1.D.F:36",)
    if deduction_refs:
        f.add("68", "Total des déductions", ei_repayment + benefit_repayments, refs=deduction_refs)
        base_refs += ("TP-1.D.F:68",)
    f.add("70", "Revenu assujetti à la cotisation", base, "ligne 36 moins ligne 68, minimum zéro",
          refs=base_refs)
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


def schedule_k(tp: Taxpayer, params: dict, quebec: Form) -> Form | None:
    """Annexe K : cotisation personnelle, selon les réponses sur le ménage et les mois exemptés.

    `compute` vérifie les renseignements avant cet appel. Les mois exemptés sont ceux de la
    partie B, même si la personne est inscrite au régime public. Le conjoint paie sa propre prime.
    """
    months = tp.drug_plan_exempt_months
    if len(months) == 12:
        return None
    t = params["quebec"]["drug_insurance"]
    status = "couple" if tp.has_spouse else "single"
    net = quebec.amount("275")
    family_income = net + (tp.spouse_net_income if tp.has_spouse else 0.0)
    base_exemption = t[f"exemption_{status}"]
    if family_income <= base_exemption:
        return None
    f = Form.from_parameters("TP-1.D.K", params)
    f.add("36", "Revenu net", net, refs=("TP-1:275",))
    family_refs = ("TP-1.D.K:36",)
    if tp.has_spouse:
        f.add("37", "Revenu net du conjoint", tp.spouse_net_income,
              "ligne 275 du TP-1 du conjoint, fournie par l'appelant")
        family_refs += ("TP-1.D.K:37",)
    f.add("40", "Revenu familial", family_income, refs=family_refs)
    f.add("41", "Exemption", base_exemption,
          params=(f"quebec.drug_insurance.exemption_{status}",))
    exemption = rules.drug_insurance_exemption(has_spouse=tp.has_spouse,
                                              dependent_children=tp.drug_plan_dependent_children, table=t)
    exemption_refs = ("TP-1.D.K:41",)
    if tp.drug_plan_dependent_children:
        number = "42" if tp.has_spouse else "44"
        count = "one" if tp.drug_plan_dependent_children == 1 else "multiple"
        f.add(number, "Exemption pour enfants à charge", exemption - base_exemption,
              "nombre d'enfants admissibles confirmé par l'appelant",
              params=(f"quebec.drug_insurance.child_exemption_{status}_{count}",))
        exemption_refs += (f"TP-1.D.K:{number}",)
    f.add("46", "Exemption totale", exemption, refs=exemption_refs)
    x = f.add("48", "Revenu servant à calculer la cotisation", max(0.0, family_income - exemption),
              refs=("TP-1.D.K:40", "TP-1.D.K:46"))
    first = sum(month <= 6 for month in months)
    second = len(months) - first
    f.add("60", "Nombre de mois exemptés de janvier à juin", first, "mois confirmés par l'appelant")
    f.add("61", "Nombre de mois exemptés de juillet à décembre", second, "mois confirmés par l'appelant")
    f.add("62", "Nombre de mois exemptés", len(months), refs=("TP-1.D.K:60", "TP-1.D.K:61"))
    width = t["first_bracket_width"]
    first_rate, second_rate = t[f"first_rate_{status}"], t[f"second_rate_{status}"]
    first_param = f"quebec.drug_insurance.first_rate_{status}"
    second_param = f"quebec.drug_insurance.second_rate_{status}"
    raw = x * first_rate if x <= width else width * first_rate + (x - width) * second_rate
    if raw >= t["rate_cap"]:
        premium = f.add("84", "Cotisation de la colonne applicable", t["rate_cap"], "plafond atteint",
                        refs=("TP-1.D.K:48",),
                        params=("quebec.drug_insurance.rate_cap", "quebec.drug_insurance.first_bracket_width",
                                first_param, second_param))
    else:
        f.add("77", "Revenu servant à calculer la cotisation", x, refs=("TP-1.D.K:48",))
        upper = x > width
        threshold = f.add("78", "Seuil de la colonne applicable", width if upper else 0.0,
                          params=("quebec.drug_insurance.first_bracket_width",))
        excess = f.add("79", "Revenu excédant le seuil", x - threshold,
                       refs=("TP-1.D.K:77", "TP-1.D.K:78"))
        rate = f.add("80", "Taux de la colonne applicable", second_rate if upper else first_rate,
                     "taux exprimé comme fraction", params=(second_param if upper else first_param,))
        f.add("81", "Cotisation sur le revenu excédentaire", excess * rate,
              refs=("TP-1.D.K:79", "TP-1.D.K:80"))
        f.add("82", "Cotisation de base de la colonne applicable", width * first_rate if upper else 0.0,
              params=("quebec.drug_insurance.first_bracket_width", first_param))
        f.add("83", "Cotisation selon le revenu", raw, "lignes 81 + 82, plafond non atteint",
              refs=("TP-1.D.K:81", "TP-1.D.K:82"), params=("quebec.drug_insurance.rate_cap",))
        premium = f.add("84", "Cotisation de la colonne applicable", raw, refs=("TP-1.D.K:83",))
    reduction = f.add("85", "Réduction pour les mois exemptés", premium * len(months) / 12,
                      "ligne 84 × ligne 62 ÷ 12", refs=("TP-1.D.K:84", "TP-1.D.K:62"))
    reduced = f.add("86", "Cotisation pour les mois non exemptés", premium - reduction,
                    refs=("TP-1.D.K:84", "TP-1.D.K:85"))
    maximum = f.add("87", "Cotisation maximale pour l'année", t["annual_maximum"],
                    params=("quebec.drug_insurance.annual_maximum",))
    maximum_reduction = f.add("88", "Réduction du maximum pour les mois exemptés",
                              first * t["monthly_maximum_first_half"] + second * t["monthly_maximum_second_half"],
                              "ligne 60 × plafond du premier semestre + ligne 61 × plafond du second semestre",
                              refs=("TP-1.D.K:60", "TP-1.D.K:61"),
                              params=("quebec.drug_insurance.monthly_maximum_first_half",
                                      "quebec.drug_insurance.monthly_maximum_second_half"))
    reduced_maximum = f.add("89", "Maximum pour les mois non exemptés", max(0.0, maximum - maximum_reduction),
                            refs=("TP-1.D.K:87", "TP-1.D.K:88"))
    amount = f.add("90", "Cotisation personnelle", min(reduced, reduced_maximum),
                   "minimum des lignes 86 et 89", refs=("TP-1.D.K:86", "TP-1.D.K:89"))
    f.add("98", "Cotisation au régime d'assurance médicaments du Québec", amount,
          "cotisation personnelle seulement; chaque conjoint paie sa propre cotisation",
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
    """TP-776.42 : base signée, rajouts des déductions visées et crédits admissibles à l’IMR."""
    t = params["quebec"]["minimum_tax"]
    inclusion = params["federal"]["capital_gains"]["inclusion_rate"]
    taxable = quebec.amount("256") - quebec.amount("295")
    enhanced, worker = quebec.amount("248"), quebec.amount("201")
    amt = rules.minimum_tax(taxable_income=taxable, capital_gains=tp.capital_gains, capital_gains_inclusion=inclusion,
                            addback_deductions=enhanced + worker, dividend_gross_up=dividend_gross_up,
                            credits=quebec.amount("399"), table=t)
    if amt.net_adjusted_taxable_income <= 0:
        return None
    f = Form.from_parameters("TP-776.42", params)
    f.add("1", "Revenu imposable", taxable, "recalcul sans plancher à zéro aux lignes 275 et 299",
          refs=("TP-1:256",) + (("TP-1:295",) if "295" in quebec.lines else ()))
    gains = f.add("10", "Ajout pour les gains en capital", tp.capital_gains * (t["capital_gains_inclusion"] - inclusion),
                  "gain réalisé × différence des taux d'inclusion",
                  refs=("TP-1:139",),
                  params=("quebec.minimum_tax.capital_gains_inclusion", "federal.capital_gains.inclusion_rate"))
    added = t["deduction_addback_rate"] * (enhanced + worker)
    if enhanced or worker:
        f.add("157.5", "Déduction pour cotisation au RRQ, au RPC ou au RQAP", enhanced,
              refs=("TP-1:248",))
        f.add("157.9", "Déduction pour travailleur", worker, refs=("TP-1:201",))
        f.add("157.11", "Total des déductions visées", enhanced + worker,
              refs=("TP-776.42:157.5", "TP-776.42:157.9"))
        f.add("157.12", "Taux applicable", t["deduction_addback_rate"], "taux exprimé comme fraction",
              params=("quebec.minimum_tax.deduction_addback_rate",))
        f.add("158", "Montant de la ligne 157.11 multiplié par 50 %", added,
              refs=("TP-776.42:157.11", "TP-776.42:157.12"))
        f.add("160", "Autres ajouts au revenu imposable", added, refs=("TP-776.42:158",))
    f.add("17", "Autres ajouts au revenu imposable", added,
          refs=("TP-776.42:160",) if enhanced or worker else ("TP-1:248", "TP-1:201"),
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


def capital_gains(tp: Taxpayer, params: dict) -> Form | None:
    """Annexe G, partie F : gain net fourni et inclusion, sans inventer de transactions."""
    if tp.capital_gains <= 0:
        return None
    f = Form.from_parameters("TP-1.D.G", params)
    net = f.add("94.1", "Gains (ou perte nette) en capital", tp.capital_gains,
                "gain net fourni avant inclusion; ventilation par bien et provisions non modélisées")
    rate = f.add("107", "Taux d'inclusion", params["federal"]["capital_gains"]["inclusion_rate"],
                 "taux exprimé comme fraction", params=("federal.capital_gains.inclusion_rate",))
    taxable = f.add("107.1", "Montant de la ligne 94.1 multiplié par le taux d'inclusion", net * rate,
                    refs=("TP-1.D.G:94.1", "TP-1.D.G:107"))
    f.add("108", "Gains en capital imposables (ou perte nette en capital)", taxable,
          "aucun gain à inclusion de 100 % dans les entrées du moteur", refs=("TP-1.D.G:107.1",))
    return f


def qpp_employment(tp: Taxpayer, params: dict, quebec: Form, qpp: rules.QppContributions) -> Form | None:
    """Annexe U, partie B : déduction du salarié québécois sans trop-perçu ni prorata mensuel.

    La ventilation des retenues simulées vient de la même règle que l'annexe 8. Les formes
    algébriques conservent exactement les montants du moteur, sans arrondir entre les lignes.
    Les cas de 18 ans ou de 73 ans et plus restent signalés hors de cette extraction.
    """
    if qpp.enhanced <= 0 or not 19 <= tp.age <= 72:
        return None
    t = params["cotisations"]["qpp"]
    f = Form.from_parameters("TP-1.D.U", params)
    withheld = quebec.amount("98")
    salary = float(min(tp.employment_income, t["maximum_pensionable_earnings"]))
    exemption = float(t["basic_exemption"])
    earnings = salary - exemption
    maximum = float(t["maximum_pensionable_earnings"])
    ceiling = max(0.0, maximum - exemption)
    pensionable = quebec.amount("98.1")
    above = max(0.0, pensionable - maximum)
    additional = float(t["additional_maximum_pensionable_earnings"])
    width = max(0.0, additional - maximum)
    # Construction groupée, comme pour les cotisations fédérales de l’annexe 8.
    f.lines = {line.number: line for line in (
        Line("10", "Cotisation au RRQ", withheld,
             refs=("TP-1:98",)),
        Line("11", "Part supplémentaire de la cotisation au RRQ", qpp.first_additional,
             "ligne 10 × taux supplémentaire / (taux de base + taux supplémentaire), sans arrondi",
             refs=("TP-1.D.U:10",),
             params=("cotisations.qpp.base_rate", "cotisations.qpp.first_additional_rate")),
        Line("12", "Salaire admissible au RRQ", salary,
             "ligne 98.1 plafonnée au maximum des gains admissibles",
             refs=("TP-1:98.1",),
             params=("cotisations.qpp.maximum_pensionable_earnings",)),
        Line("13", "Exemption personnelle au RRQ", exemption,
             "montant annuel, sans prorata mensuel",
             params=("cotisations.qpp.basic_exemption",)),
        Line("14", "Montant de la ligne 12 moins celui de la ligne 13", earnings,
             refs=("TP-1.D.U:12", "TP-1.D.U:13")),
        Line("14.1", "Maximum des gains admissibles", maximum,
             params=("cotisations.qpp.maximum_pensionable_earnings",)),
        Line("14.2", "Montant de la ligne 13", exemption,
             refs=("TP-1.D.U:13",)),
        Line("14.3", "Montant de la ligne 14.1 moins celui de la ligne 14.2", ceiling,
             refs=("TP-1.D.U:14.1", "TP-1.D.U:14.2")),
        Line("14.4", "Moins élevé des montants des lignes 14 et 14.3", min(earnings, ceiling),
             refs=("TP-1.D.U:14", "TP-1.D.U:14.3")),
        Line("15", "Première cotisation supplémentaire maximale", qpp.first_additional,
             refs=("TP-1.D.U:14.4",),
             params=("cotisations.qpp.first_additional_rate",)),
        Line("16", "Moins élevé des montants des lignes 11 et 15", qpp.first_additional,
             refs=("TP-1.D.U:11", "TP-1.D.U:15")),
        Line("17", "Cotisation au RRQ", withheld,
             refs=("TP-1:98",)),
        Line("17.1", "Montant de la ligne 14.4", min(earnings, ceiling),
             refs=("TP-1.D.U:14.4",)),
        Line("17.2", "Cotisation de base et première cotisation supplémentaire requises", qpp.base + qpp.first_additional,
             "somme des deux composantes non arrondies",
             refs=("TP-1.D.U:17.1",),
             params=("cotisations.qpp.base_rate", "cotisations.qpp.first_additional_rate")),
        Line("17.3", "Montant de la ligne 17 moins celui de la ligne 17.2", 0.0,
             "retenues simulées égales aux cotisations requises",
             refs=("TP-1.D.U:17", "TP-1.D.U:17.2")),
        Line("17.4", "Cotisation supplémentaire au RRQ", qpp.second_additional,
             refs=("TP-1:98.2",)),
        Line("17.5", "Total des montants des lignes 17.3 et 17.4", qpp.second_additional,
             refs=("TP-1.D.U:17.3", "TP-1.D.U:17.4")),
        Line("18.5", "Salaire admissible au RRQ", pensionable,
             refs=("TP-1:98.1",)),
        Line("18.6", "Montant de la ligne 14.1", maximum,
             refs=("TP-1.D.U:14.1",)),
        Line("18.7", "Montant de la ligne 18.5 moins celui de la ligne 18.6", above,
             refs=("TP-1.D.U:18.5", "TP-1.D.U:18.6")),
        Line("18.8", "Maximum supplémentaire des gains admissibles", additional,
             params=("cotisations.qpp.additional_maximum_pensionable_earnings",)),
        Line("18.9", "Montant de la ligne 14.1", maximum,
             refs=("TP-1.D.U:14.1",)),
        Line("19", "Montant de la ligne 18.8 moins celui de la ligne 18.9", width,
             refs=("TP-1.D.U:18.8", "TP-1.D.U:18.9")),
        Line("20", "Moins élevé des montants des lignes 18.7 et 19", min(above, width),
             refs=("TP-1.D.U:18.7", "TP-1.D.U:19")),
        Line("21", "Deuxième cotisation supplémentaire maximale", qpp.second_additional,
             refs=("TP-1.D.U:20",),
             params=("cotisations.qpp.second_additional_rate",)),
        Line("22", "Moins élevé des montants des lignes 17.5 et 21", qpp.second_additional,
             refs=("TP-1.D.U:17.5", "TP-1.D.U:21")),
        Line("22.1", "Montant de la ligne 16", qpp.first_additional,
             refs=("TP-1.D.U:16",)),
        Line("23", "Déduction pour cotisation au RRQ pour un revenu d'emploi", qpp.enhanced,
             refs=("TP-1.D.U:22", "TP-1.D.U:22.1")),
    )}
    return f
