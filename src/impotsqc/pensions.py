# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Revenus de pension et choix distincts de fractionnement fédéral et québécois."""

from __future__ import annotations

from .inputs import CoupleOptions, PensionSplit
from .model import Form, Taxpayer


def pension_amounts(tp: Taxpayer, params: dict) -> tuple[float, float, float, float]:
    """Ventile les pensions vers 11500, les rentes REER, 13000 et les rentes admissibles.

    Les rentes RPA sont admissibles à tout âge. Les FERR/rentes REER le sont à 65 ans,
    ou lorsqu'ils découlent du décès du conjoint. PSV/RRQ et retraits REER non échus sont exclus.
    """
    minimum_age = params["federal"]["pension_amount"]["minimum_age_for_rrif"]
    rrif_65 = tp.rrif_income if tp.age >= minimum_age else 0.0
    pension_income, rrsp_annuities, other_rrif = rrif_65, 0.0, tp.rrif_income - rrif_65
    eligible_annuity = 0.0
    for pension in tp.pensions:
        eligible = tp.age >= minimum_age or pension.from_deceased_spouse
        if pension.kind == "rpp":
            pension_income += pension.amount
        elif pension.kind == "rrsp_annuity":
            rrsp_annuities += pension.amount
            if eligible:
                eligible_annuity += pension.amount
        elif eligible:
            pension_income += pension.amount
        else:
            other_rrif += pension.amount
    return pension_income, rrsp_annuities, other_rrif, eligible_annuity


def split_questions(first: Taxpayer, second: Taxpayer, options: CoupleOptions, params: dict) -> dict[str, str]:
    """Demande les confirmations et retenues nécessaires aux choix exprimés, sans les présumer."""
    questions = {}
    for regime in ("federal", "quebec"):
        field = f"{regime}_pension_split"
        choice = getattr(options, field)
        if choice is None or choice.amount == 0:
            continue
        prefix = f"options.{field}."
        if choice.eligible is False:
            raise ValueError(f"{field} : un choix de fractionnement exige une admissibilité confirmée")
        if choice.eligible is None:
            questions[prefix + "eligible"] = (
                "Confirmez le choix conjoint et les conditions du T1032 : résidence canadienne des deux "
                "personnes au 31 décembre ou au décès, absence de rupture de 90 jours incluant le 31 décembre. "
                "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t1032/t1032-25f.pdf"
                if regime == "federal" else
                "Confirmez le choix conjoint de l'annexe Q : conjoint québécois au 31 décembre, "
                "cédant de 65 ans ou plus et deux déclarations de résidents du Québec. "
                "https://www.revenuquebec.ca/documents/fr/formulaires/tp/2025-12/TP-1.D.Q%282025-12%29.pdf")
        if choice.tax_withheld is None:
            questions[prefix + "tax_withheld"] = (
                f"Quel impôt {regime} a été retenu sur les seules pensions admissibles du cédant, "
                "avant fractionnement ? Confirmez zéro s'il n'y en a aucun; ventilez les feuillets mixtes.")
        if regime == "federal":
            if choice.months_as_spouses is None:
                questions[prefix + "months_as_spouses"] = "Pendant combien de mois étiez-vous mariés ou conjoints de fait dans l'année ?"
            if choice.tax_year_months is None:
                questions[prefix + "tax_year_months"] = (
                    "Combien de mois compte l'année fiscale du cédant pour le T1032 : 12, ou le nombre "
                    "de mois jusqu'au décès, y compris le mois du décès ?")
            donor, recipient = (first, second) if choice.donor == "first" else (second, first)
            table = params["federal"]["pension_amount"]
            own = pension_amounts(recipient, params)
            rpp = sum(p.amount for p in donor.pensions if p.kind == "rpp")
            possible_survivor = donor.rrif_income + sum(p.amount for p in donor.pensions
                if p.kind != "rpp" and p.from_deceased_spouse is not False)
            if (recipient.age < table["minimum_age_for_rrif"] <= donor.age
                    and own[0] + own[3] < table["maximum"] and possible_survivor > 0
                    and rpp < params["federal"]["pension_split"]["recipient_recalculation_threshold"]
                    and choice.same_year_survivor_pension is None):
                questions[prefix + "same_year_survivor_pension"] = (
                    "Quelle part des FERR/rentes REER du cédant découle du décès d'un conjoint survenu "
                    "pendant cette année fiscale ? Confirmez zéro si aucun. La note 1 du T1032 en a "
                    "besoin pour le crédit du bénéficiaire de moins de 65 ans; une pension de survivant "
                    "sans année du décès ne suffit pas. "
                    "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t1032/t1032-25f.pdf")
        for name, person in (("first", first), ("second", second)):
            if person.payments is None:
                questions[f"{name}.payments"] = (
                    "Confirmez les retenues d'impôt fédéral/Québec et les acomptes, y compris zéro, "
                    "dans TaxPayments. Les retenues totales ne se déduisent pas du revenu de pension.")
    return questions


def federal_split(donor: Taxpayer, recipient: Taxpayer, choice: PensionSplit, params: dict) -> Form | None:
    """T1032, pensions RPA/FERR/rentes REER et prorata, crédits et retenues obligatoires.

    Les conventions de retraite, prestations de vétérans et transferts directs exclus du
    crédit de pension requièrent encore leurs entrées propres; aucun montant n'est inventé.
    Les deux déclarations reçoivent les mêmes montants, avec des références adaptées à leur rôle.
    """
    if choice.amount == 0:
        return None
    table = params["federal"]["pension_split"]
    minimum_age = params["federal"]["pension_amount"]["minimum_age_for_rrif"]
    a = pension_amounts(donor, params)
    b = pension_amounts(recipient, params)
    eligible, recipient_own = a[0] + a[3], b[0] + b[3]
    possible_survivor = donor.rrif_income + sum(p.amount for p in donor.pensions
        if p.kind != "rpp" and p.from_deceased_spouse is not False)
    if (choice.same_year_survivor_pension is not None
            and choice.same_year_survivor_pension > possible_survivor):
        raise ValueError("les pensions liées à un décès dans l'année dépassent les FERR/rentes de survivant possibles")
    prorata = choice.months_as_spouses / choice.tax_year_months
    maximum = eligible * prorata * table["maximum_fraction"]
    if choice.amount > maximum:
        raise ValueError(f"fractionnement fédéral supérieur au maximum admissible de {maximum:.2f} $")
    if choice.tax_withheld > donor.payments.federal_withheld:
        raise ValueError("les retenues de pension fédérales dépassent les retenues fédérales totales")
    f = Form.from_parameters("T1032", params)
    f.add("68020", "Revenu de pension admissible", eligible,
          "ligne 8 de la grille 31400 du cédant")
    f.add("3", "Ligne 1 moins ligne 2", eligible, "aucune prestation de vétérans saisie", refs=("T1032:68020",))
    f.add("17", "Total du revenu de pension admissible", eligible, "aucune convention de retraite ni prestation de vétérans saisie",
          refs=("T1032:3",))
    f.add("68030", "Nombre de mois marié ou conjoint de fait", choice.months_as_spouses, "réponse explicite des déclarants")
    f.add("18", "Revenu admissible après changement d'état civil", eligible * prorata,
          f"mois comme conjoints divisés par {choice.tax_year_months} mois dans l'année fiscale, multipliés par ligne 17",
          refs=("T1032:68030", "T1032:17"))
    f.add("19", "Revenu de pension admissible après rajustement", eligible * prorata, refs=("T1032:18",))
    f.add("20", "Taux maximal", table["maximum_fraction"], "taux exprimé comme fraction",
          params=("federal.pension_split.maximum_fraction",))
    f.add("21", "Montant de pension fractionné maximal", maximum, refs=("T1032:19", "T1032:20"))
    f.add("22", "Montant de pension fractionné choisi", choice.amount, "choix conjoint, au plus le montant de la ligne 21",
          refs=("T1032:21",))
    f.add("23", "Montant de la ligne 1", eligible, refs=("T1032:68020",))
    f.add("30", "Montant de pension attribué au conjoint", choice.amount, "aucune portion de convention de retraite",
          refs=("T1032:22",))
    f.add("31", "Revenu de pension admissible du cédant après transfert", eligible - choice.amount,
          refs=("T1032:23", "T1032:30"))
    f.add("32", "Revenu de pension admissible propre au bénéficiaire", recipient_own,
          "ligne 8 de sa grille 31400, avant transfert",
          params=("federal.pension_amount.minimum_age_for_rrif",))
    received_credit = choice.amount
    if (recipient.age < minimum_age <= donor.age
            and recipient_own < params["federal"]["pension_amount"]["maximum"]):
        at_any_age = sum(p.amount for p in donor.pensions if p.kind == "rpp") + (choice.same_year_survivor_pension or 0.0)
        if at_any_age < table["recipient_recalculation_threshold"]:
            received_credit = min(choice.amount, at_any_age * prorata * table["maximum_fraction"])
    f.add("33", "Pension transférée admissible au montant pour revenu de pension", received_credit,
          "étape 4, note 1 : nouvelle limite selon les types de pension et l'âge du bénéficiaire",
          refs=("T1032:30", "T1032:68020", "T1032:32", "T1032:68030"),
          params=("federal.pension_split.recipient_recalculation_threshold", "federal.pension_split.maximum_fraction",
                  "federal.pension_amount.minimum_age_for_rrif", "federal.pension_amount.maximum"))
    f.add("34", "Revenu de pension admissible du bénéficiaire après transfert", recipient_own + received_credit,
          refs=("T1032:32", "T1032:33"))
    f.add("68040", "Impôt retenu sur les pensions admissibles du cédant", choice.tax_withheld,
          "retenues admissibles fournies, après ventilation des feuillets mixtes")
    transferred_tax = choice.tax_withheld * choice.amount / eligible
    f.add("68050", "Impôt retenu sur le montant de pension fractionné", transferred_tax,
          "ligne 35 multipliée par ligne 22, divisée par ligne 17",
          refs=("T1032:68040", "T1032:22", "T1032:17"))
    f.add("37", "Impôt total initialement retenu du cédant", donor.payments.federal_withheld,
          "retenues initiales des feuillets, hors impôt du Québec")
    f.add("38", "Impôt retenu transféré", transferred_tax, refs=("T1032:68050",))
    f.add("39", "Impôt total retenu du cédant après transfert", donor.payments.federal_withheld - transferred_tax,
          refs=("T1032:37", "T1032:38"))
    f.add("40", "Impôt total initialement retenu du bénéficiaire", recipient.payments.federal_withheld,
          "retenues initiales des feuillets, hors impôt du Québec")
    f.add("41", "Impôt retenu reçu", transferred_tax, refs=("T1032:68050",))
    f.add("42", "Impôt total retenu du bénéficiaire après transfert", recipient.payments.federal_withheld + transferred_tax,
          refs=("T1032:40", "T1032:41"))
    return f


def quebec_split(donor: Taxpayer, choice: PensionSplit, params: dict) -> Form | None:
    """Annexe Q : transfert choisi et impôt retenu dans la même proportion, à partir de 65 ans."""
    if choice.amount == 0:
        return None
    table = params["quebec"]["pension_split"]
    if donor.age < table["minimum_age"]:
        raise ValueError("le cédant doit avoir au moins 65 ans pour le transfert québécois")
    eligible = donor.rrif_income + sum(p.amount for p in donor.pensions)
    if choice.amount > eligible * table["maximum_fraction"]:
        raise ValueError("fractionnement québécois supérieur à 50 % du revenu admissible")
    if choice.tax_withheld > donor.payments.quebec_withheld:
        raise ValueError("les retenues de pension québécoises dépassent les retenues québécoises totales")
    f = Form.from_parameters("TP-1.D.Q", params)
    f.add("10", "Revenus de retraite", eligible, "pensions canadiennes saisies; aucune convention de retraite",
          refs=("TP-1:122",))
    f.add("18", "Total des déductions des lignes 12 à 16", 0.0,
          "aucun transfert direct, remboursement de cotisation RPAC ni revenu exonéré saisi")
    f.add("20", "Revenus de retraite admissibles au transfert", eligible,
          refs=("TP-1.D.Q:10", "TP-1.D.Q:18"))
    f.add("22", "Revenus de retraite transférés au conjoint", choice.amount, "choix conjoint, au plus 50 % de la ligne 20",
          refs=("TP-1.D.Q:20",), params=("quebec.pension_split.maximum_fraction", "quebec.pension_split.minimum_age"))
    f.add("50", "Impôt du Québec retenu sur les revenus admissibles", choice.tax_withheld,
          "part admissible de la case J du relevé 2, fournie par le cédant")
    f.add("52", "Montant de la ligne 22", choice.amount, refs=("TP-1.D.Q:22",))
    f.add("53", "Montant de la ligne 20", eligible, refs=("TP-1.D.Q:20",))
    f.add("58", "Impôt du Québec retenu transféré au conjoint", choice.tax_withheld * choice.amount / eligible,
          "ligne 50 multipliée par ligne 52, divisée par ligne 53",
          refs=("TP-1.D.Q:50", "TP-1.D.Q:52", "TP-1.D.Q:53"))
    return f
