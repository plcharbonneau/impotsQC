# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Déclarations coordonnées : revenus de pension, droits familiaux, crédits et retenues."""

from __future__ import annotations

from dataclasses import replace
from math import isfinite

from . import federal_schedules, rules
from .federal import federal_income, federal_personal_credits, federal_tax
from .inputs import CoupleOptions
from .model import CoupleReturn, Taxpayer, TaxReturn
from .pensions import federal_split, quebec_split, split_questions
from .payments import settle_tax_payments
from .quebec import quebec_income, quebec_personal_credits, quebec_final_tax
from .questions import MissingInformationError, required_questions


def required_couple_questions(first: Taxpayer, second: Taxpayer, *,
                              options: CoupleOptions | None = None) -> dict[str, str]:
    """Questions de chaque personne; le revenu du conjoint sera fourni par sa déclaration.

    Les deux personnes doivent confirmer leur statut de conjoints fiscaux au Québec. Le nom
    de cette fonction ne permet pas de présumer leur admissibilité. Les clés sont préfixées
    par `first.` ou `second.` pour guider un questionnaire sans ambiguïté.
    """
    if first.year != second.year:
        raise ValueError("les deux déclarations doivent viser la même année")
    questions = {}
    for name, taxpayer in (("first", first), ("second", second)):
        if taxpayer.has_spouse is False:
            raise ValueError(f"{name}.has_spouse=False : utiliser compute pour une déclaration indépendante")
        for key, question in required_questions(taxpayer).items():
            if key != "spouse_net_income":
                questions[f"{name}.{key}"] = question
    options = options if options is not None else CoupleOptions()
    if not isinstance(options, CoupleOptions):
        raise ValueError("options doit être un objet CoupleOptions")
    if options.spouse_amount_claimant is None:
        questions["options.spouse_amount_claimant"] = (
            "Qui demande le montant fédéral pour conjoint : first, second ou neither ? "
            "Le demandeur doit avoir subvenu aux besoins du conjoint et remplir les conditions "
            "de l'annexe 5; un faible revenu ne suffit pas à lui seul. Un seul demandeur est permis. "
            "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5000-s5/5000-s5-25f.pdf")
    if options.spouse_amount_claimant in ("first", "second") and options.spouse_caregiver is None:
        questions["options.spouse_caregiver"] = (
            "Le conjoint soutenu est-il à la charge du demandeur en raison d'une infirmité "
            "mentale ou physique admissible au crédit canadien pour aidant ? Confirmez True ou False; "
            "l'admissibilité fiscale et les justificatifs de l'annexe 5 doivent être vérifiés.")
    if options.federal_transfers is None:
        questions["options.federal_transfers"] = (
            "Les transferts fédéraux de l'annexe 2 sont-ils admissibles et demandés ? "
            "Confirmez True ou False, notamment selon le statut fédéral de conjoint et la règle "
            "de séparation pour rupture pendant 90 jours ou plus incluant le 31 décembre. "
            "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5005-s2/5005-s2-25f.pdf")
    if options.federal_pension_split is not None or options.quebec_pension_split is not None:
        from . import _params
        questions.update(split_questions(first, second, options, _params(first.year)))
    return questions


def compute_couple(first: Taxpayer, second: Taxpayer, *, schedule_b_first_share: float = 0.5,
                   options: CoupleOptions | None = None) -> CoupleReturn:
    """Calcule les revenus des conjoints, leur RAMQ et leur annexe B commune puis répartie.

    `schedule_b_first_share` est la fraction du montant commun demandée par la première
    personne (de 0 à 1). Le partage par défaut est égal; aucune optimisation n’est présumée.
    `options` confirme l’admissibilité aux montants et transferts fédéraux; les réponses
    inconnues bloquent le calcul. Les choix de fractionnement fédéral/Québec sont distincts.
    Les revenus tiennent compte du choix avant le remboursement des prestations, les droits
    personnels, les transferts de crédits et l’impôt final; aucun formulaire complet jetable.
    """
    from . import _params, _warnings

    share = schedule_b_first_share
    if type(share) not in (int, float) or not isfinite(share) or not 0 <= share <= 1:
        raise ValueError("schedule_b_first_share doit être un nombre fini entre 0 et 1")
    params = _params(first.year)
    options = options if options is not None else CoupleOptions()
    questions = required_couple_questions(first, second, options=options)
    if questions:
        raise MissingInformationError(questions)
    prepared = [{}, {}]
    refs = {}
    names = ("first", "second")
    taxpayers = (first, second)
    federal_choice = options.federal_pension_split
    quebec_choice = options.quebec_pension_split
    federal_donor = quebec_donor = None
    if federal_choice is not None and federal_choice.amount:
        federal_donor = names.index(federal_choice.donor)
        other = 1 - federal_donor
        annex = federal_split(taxpayers[federal_donor], taxpayers[other], federal_choice, params)
        for index, name in enumerate(names):
            copy = replace(annex, lines=dict(annex.lines))
            prepared[index]["T1032"] = copy
            if index == federal_donor:
                copy.lines["68020"] = copy["68020"]._replace(refs=("5000-D1:31400-8",))
            else:
                refs[f"{name}/T1032:68020"] = (f"{names[federal_donor]}/5000-D1:31400-8",)
            if annex.amount("32"):
                if index == other:
                    copy.lines["32"] = copy["32"]._replace(refs=("5000-D1:31400-8",))
                else:
                    refs[f"{name}/T1032:32"] = (f"{names[other]}/5000-D1:31400-8",)
    if quebec_choice is not None and quebec_choice.amount:
        quebec_donor = names.index(quebec_choice.donor)
        prepared[quebec_donor]["TP-1.D.Q"] = quebec_split(taxpayers[quebec_donor], quebec_choice, params)
        other = names[1 - quebec_donor]
        refs[f"{other}/TP-1:123"] = (f"{names[quebec_donor]}/TP-1.D.Q:22",)
        refs[f"{other}/TP-1:451.3"] = (f"{names[quebec_donor]}/TP-1.D.Q:58",)
    for index, taxpayer in enumerate(taxpayers):
        forms = prepared[index]
        recipient = federal_donor is not None and index != federal_donor
        qpp = rules.qpp_contributions(taxpayer.employment_income, params["cotisations"]["qpp"])
        federal = federal_income(taxpayer, params, qpp, forms=forms, split_recipient=recipient)
        federal_personal_credits(taxpayer, params, qpp, forms=forms, coordinated=options.federal_transfers,
                                 split_recipient=recipient)
        received = quebec_choice.amount if quebec_donor is not None and index != quebec_donor else 0.0
        quebec_income(taxpayer, params, qpp, federal.amount("23500"), forms=forms, pension_received=received)
    people = []
    for index, taxpayer in enumerate((first, second)):
        spouse_net = prepared[1 - index]["TP-1"].amount("275")
        supplied = taxpayer.spouse_net_income
        if supplied is not None and round(supplied, 2) != round(spouse_net, 2):
            name = "first" if index == 0 else "second"
            raise ValueError(f"{name}.spouse_net_income ne correspond pas à la ligne 275 du conjoint")
        people.append(replace(taxpayer, spouse_net_income=spouse_net))
    # Les revenus sont définitifs; les crédits sont encore à remplir dans ces mêmes objets Form.
    results = [TaxReturn(tp, forms) for tp, forms in zip(people, prepared)]
    for index, result in enumerate(results):
        name, other = ("first", "second") if index == 0 else ("second", "first")
        spouse = results[1 - index].federal
        if options.spouse_amount_claimant == name:
            annex = federal_schedules.spouse_amount(params, result.federal, spouse, caregiver=options.spouse_caregiver)
            if annex is not None:
                result.forms[annex.code] = annex
                result.federal.add("30300", "Montant pour époux ou conjoint de fait", annex.amount("30300-5"),
                                   refs=("5000-S5:30300-5",))
                refs[f"{name}/5000-S5:30300-4"] = (f"{other}/T1:23600",)
                if "30425-5" in annex.lines:
                    result.federal.add("30425", "Montant canadien pour aidant naturel pour époux ou conjoint de fait",
                                       annex.amount("30425-5"), refs=("5000-S5:30425-5",))
        if options.federal_transfers:
            annex = federal_schedules.spouse_transfer(params, spouse)
            if annex is not None:
                result.forms[annex.code] = annex
                result.federal.add("32600", "Montants transférés de votre époux ou conjoint de fait", annex.amount("13"),
                                   refs=("5005-S2:13",))
                for source, target in (("35200", "30100"), ("35500", "31400"), ("8", "30000"), ("9", "100")):
                    refs[f"{name}/5005-S2:{source}"] = (f"{other}/T1:{target}",)
                source = "26000" if spouse.amount("26000") <= params["federal"]["brackets"]["thresholds"][0] else "40400"
                refs[f"{name}/5005-S2:7"] = (f"{other}/T1:{source}",)
        federal_tax(result.taxpayer, params, forms=result.forms)
    for index, result in enumerate(results):
        quebec_personal_credits(result.taxpayer, params, forms=result.forms, spouse=results[1 - index],
                   schedule_b_share=share if index == 0 else 1 - share)
    if options.transfer_unused_quebec:
        for index, donor in enumerate(results):
            receiver = results[1 - index]
            if donor.quebec.amount("430") < 0 < receiver.quebec.amount("430"):
                amount = -donor.quebec.amount("430")
                donor.quebec.add("431", "Crédits transférés d'un conjoint à l'autre", -amount,
                                 "crédits cédés : report du solde négatif de la ligne 430", refs=("TP-1:430",))
                receiver.quebec.add("431", "Crédits transférés d'un conjoint à l'autre", amount,
                                    "crédits reçus : valeur absolue du solde négatif du conjoint; déduite à la ligne 432")
                source, target = ("first", "second") if index == 0 else ("second", "first")
                refs[f"{target}/TP-1:431"] = (f"{source}/TP-1:430",)
    for index, result in enumerate(results):
        quebec_final_tax(result.taxpayer, params, forms=result.forms, spouse=results[1 - index])
        received = (prepared[quebec_donor]["TP-1.D.Q"].amount("58")
                    if quebec_donor is not None and index != quebec_donor else None)
        settle_tax_payments(result.taxpayer, result.forms,
                            federal_recipient=federal_donor is not None and index != federal_donor,
                            quebec_received=received)
    for index, name in enumerate(("first", "second")):
        other = "second" if index == 0 else "first"
        result = results[index]
        for code, number, target in (("TP-1.D.B", "12", "275"), ("TP-1.D.B", "1.C", "122"),
                                      ("TP-1.D.B", "6.C", "245"),
                                      ("TP-1.D.K", "37", "275"), ("TP-776.42", "270", "399"),
                                      ("TP-776.42", "271", "391"), ("TP-776.42", "277", "401"),
                                      ("TP-776.42", "287", "425")):
            if code in result.forms and number in result.forms[code].lines:
                form = result.forms[code]
                line = form[number]
                form.lines[number] = line._replace(rule=f"ligne {target} du TP-1 du conjoint; lien dans CoupleReturn.refs")
                refs[f"{name}/{code}:{number}"] = (f"{other}/TP-1:{target}",)
                if code == "TP-1.D.B" and number == "1.C" and "123" in results[1 - index].quebec.lines:
                    refs[f"{name}/{code}:{number}"] += (f"{other}/TP-1:123",)
                    form.lines[number] = line._replace(rule="total des lignes 122 et 123 du conjoint; liens dans CoupleReturn.refs")
        warnings = _warnings(result.taxpayer, params, result.forms, coordinated=True)
        if federal_donor is not None and federal_choice.tax_year_months < 12:
            warnings += ("Décès : le prorata du T1032 est calculé; les autres règles des déclarations "
                         "d'une personne décédée ne sont pas toutes modélisées.",)
        results[index] = TaxReturn(result.taxpayer, result.forms, warnings)
    return CoupleReturn(results[0], results[1], refs, options=options, schedule_b_first_share=share)
