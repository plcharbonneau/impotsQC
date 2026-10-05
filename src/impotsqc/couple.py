# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Coordination des revenus familiaux et du partage de l’annexe B, sans saisie en double."""

from __future__ import annotations

from dataclasses import replace
from math import isfinite

from . import rules
from .federal import federal_return
from .model import CoupleReturn, Taxpayer, TaxReturn
from .quebec import quebec_income, quebec_tax
from .questions import MissingInformationError, required_questions


def required_couple_questions(first: Taxpayer, second: Taxpayer) -> dict[str, str]:
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
    return questions


def compute_couple(first: Taxpayer, second: Taxpayer, *, schedule_b_first_share: float = 0.5) -> CoupleReturn:
    """Calcule les revenus des conjoints, leur RAMQ et leur annexe B commune puis répartie.

    `schedule_b_first_share` est la fraction du montant commun demandée par la première
    personne (de 0 à 1). Le partage par défaut est égal; aucune optimisation n’est présumée.
    Les montants pour conjoint, transferts de crédits inutilisés et fractionnement de pension
    restent à implémenter et sont signalés dans chaque déclaration. Aucun formulaire provisoire
    n’est construit : les deux revenus précèdent les deux calculs de crédits.
    """
    from . import _params, _warnings

    share = schedule_b_first_share
    if type(share) not in (int, float) or not isfinite(share) or not 0 <= share <= 1:
        raise ValueError("schedule_b_first_share doit être un nombre fini entre 0 et 1")
    params = _params(first.year)
    questions = required_couple_questions(first, second)
    if questions:
        raise MissingInformationError(questions)
    prepared = []
    for taxpayer in (first, second):
        forms = {}
        qpp = rules.qpp_contributions(taxpayer.employment_income, params["cotisations"]["qpp"])
        federal = federal_return(taxpayer, params, qpp, forms=forms)
        quebec_income(taxpayer, params, qpp, federal.amount("23500"), forms=forms)
        prepared.append(forms)
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
        quebec_tax(result.taxpayer, params, forms=result.forms, spouse=results[1 - index],
                   schedule_b_share=share if index == 0 else 1 - share)
    refs = {}
    for index, name in enumerate(("first", "second")):
        other = "second" if index == 0 else "first"
        result = results[index]
        for code, number, target in (("TP-1.D.B", "12", "275"), ("TP-1.D.B", "1.C", "122"),
                                      ("TP-1.D.K", "37", "275")):
            if code in result.forms and number in result.forms[code].lines:
                form = result.forms[code]
                line = form[number]
                form.lines[number] = line._replace(rule=f"ligne {target} du TP-1 du conjoint; lien dans CoupleReturn.refs")
                refs[f"{name}/{code}:{number}"] = (f"{other}/TP-1:{target}",)
        results[index] = TaxReturn(result.taxpayer, result.forms,
                                  _warnings(result.taxpayer, params, result.forms, coordinated=True))
    return CoupleReturn(results[0], results[1], refs)
