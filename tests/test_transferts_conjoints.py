# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Crédits de conjoint et transferts, vérifiés sur les grilles fédérales et québécoises."""

import json
from dataclasses import replace

import pytest

from impotsqc import (Benefits, CoupleOptions, MissingInformationError, PensionIncome, Taxpayer, compute,
                      compute_couple, required_couple_questions)
from test_formulaires import (test_metadonnees_et_alias as check_metadata,
                              test_references_et_parametres_resolvent as check_local_refs,
                              test_reports_des_annexes as check_annexes)


def person(**values):
    """Contribuable fictif avec statut québécois et assurance privée confirmés."""
    return Taxpayer(**(dict(year=2025, age=40, has_spouse=True,
                           drug_plan_exempt_months=tuple(range(1, 13))) | values))


def options(**values):
    """Choix explicites, sans demande de montant pour conjoint par défaut du scénario."""
    return CoupleOptions(**(dict(spouse_amount_claimant="neither", federal_transfers=True) | values))


def assert_graph(pair):
    """Résout les références des deux déclarations, avec détection des cycles familiaux."""
    graph = {}
    for name, result in (("first", pair.first), ("second", pair.second)):
        check_metadata(result)
        check_local_refs(result)
        check_annexes(result)
        for code, form in result.forms.items():
            for number, line in form.lines.items():
                key = f"{name}/{code}:{number}"
                graph[key] = tuple(f"{name}/{ref}" for ref in line.refs) + pair.refs.get(key, ())
    assert set(pair.refs) <= set(graph)
    visited = set()

    def visit(node, path):
        """Vérifie un nœud et toutes ses dépendances."""
        assert node not in path
        if node not in visited:
            for target in graph[node]:
                assert target in graph
                visit(target, path + (node,))
            visited.add(node)

    for node in graph:
        visit(node, ())
    data = json.loads(json.dumps(pair.to_dict(), ensure_ascii=False))
    assert data["options"]["federal_transfers"] is pair.options.federal_transfers
    assert data["summary"]["total_payable"] == round(pair.total_payable, 2)


@pytest.mark.parametrize("year,bpa,qc_bpa,rate", ((2025,16129,18571,0.145),(2026,16452,18952,0.14)))
def test_conjoint_sans_revenu(year, bpa, qc_bpa, rate):
    """Un seul revenu de 50 000 $; les deux montants de base sont utilisables selon les choix."""
    choice = options(spouse_amount_claimant="first", spouse_caregiver=False)
    pair = compute_couple(person(year=year, interest_income=50_000), person(year=year), options=choice)
    a, b = pair.first, pair.second
    s5 = a.forms["5000-S5"]
    assert s5.amount("30300-5") == a.federal.amount("30300") == bpa
    assert a.federal.amount("33800") == pytest.approx(2 * bpa * rate)
    assert a.federal.amount("40600") == pytest.approx((50_000 - 2 * bpa) * rate)
    assert b.quebec.amount("413") == pytest.approx(-qc_bpa * 0.14)
    assert b.quebec.amount("431") == b.quebec.amount("430")
    assert a.quebec.amount("431") == pytest.approx(qc_bpa * 0.14)
    assert a.quebec.amount("432") == pytest.approx((50_000 - 2 * qc_bpa) * 0.14)
    assert b.quebec.amount("432") == 0
    assert pair.refs["first/TP-1:431"] == ("second/TP-1:430",)
    assert "5005-S2" not in a.forms
    assert_graph(pair)


@pytest.mark.parametrize("income,spouse_amount,caregiver", ((0,18816,0),(9000,9816,0),(20000,0,8601),(25000,0,3798),(28798,0,0),(28799,0,0)))
def test_conjoint_aidant_2025(income, spouse_amount, caregiver):
    """S5 2025 : 2 687 $ de supplément, plafond 8 601 $, extinction à 28 798 $."""
    pair = compute_couple(person(interest_income=50_000), person(interest_income=income),
                          options=options(spouse_amount_claimant="first", spouse_caregiver=True))
    assert pair.first.federal.amount("30300") == spouse_amount
    assert pair.first.federal.amount("30425") == caregiver
    assert ("5000-S5" in pair.first.forms) == bool(spouse_amount or caregiver)
    assert_graph(pair)


def test_montant_base_du_demandeur_a_revenu_eleve():
    """Le montant 30300 utilise le montant personnel réduit du demandeur, pas le maximum annuel."""
    pair = compute_couple(person(interest_income=300_000), person(),
                          options=options(spouse_amount_claimant="first", spouse_caregiver=False))
    assert pair.first.federal.amount("30300") == 14_538
    assert pair.first.forms["5000-S5"].amount("30300-1") == 14_538
    assert_graph(pair)


def test_aidant_2026_valeurs_publiees():
    """Le TD1 2026 publie 2 740 $, sans réindexer arbitrairement le supplément 2025 arrondi."""
    pair = compute_couple(person(year=2026, interest_income=50_000), person(year=2026),
                          options=options(spouse_amount_claimant="first", spouse_caregiver=True))
    assert pair.first.forms["5000-S5"].amount("51090") == 2_740
    assert pair.first.federal.amount("30300") == 19_192
    pair = compute_couple(person(year=2026, interest_income=50_000), person(year=2026, interest_income=25_000),
                          options=options(spouse_amount_claimant="first", spouse_caregiver=True))
    assert pair.first.federal.amount("30425") == 4_374


@pytest.mark.parametrize("year,expected", ((2025,2157),(2026,2660)))
def test_transfert_pension_age_non_utilises(year, expected):
    """S2 : revenu 25 000 $, pension 2 000 $, droit d’âge et base propres à l’année."""
    pair = compute_couple(person(year=year, interest_income=50_000), person(year=year, age=66, rrif_income=25_000),
                          options=options())
    annex = pair.first.forms["5005-S2"]
    assert annex.amount("7") == 25_000
    assert annex.amount("35500") == 2_000
    assert annex.amount("13") == pair.first.federal.amount("32600") == expected
    assert pair.first.federal["32600"].refs == ("5005-S2:13",)
    assert "5005-S2" not in pair.second.forms
    assert_graph(pair)


@pytest.mark.parametrize("pension,expected", ((PensionIncome(3000,"rpp"),2000),(PensionIncome(3000,"rrif",False),0),(PensionIncome(3000,"rrif",True),2000)))
def test_transfert_retraite_avant_65_ans(pension, expected):
    """La pension transférable suit l’admissibilité au montant 31400, sans exiger 65 ans pour un RPA."""
    pair = compute_couple(person(interest_income=50_000), person(pensions=(pension,)), options=options())
    assert pair.first.federal.amount("32600") == expected
    assert ("5005-S2" in pair.first.forms) == bool(expected)
    assert_graph(pair)


def test_annexe2_cotisations_et_non_double_compte():
    """La ligne 100 protège les crédits du donneur avant de consommer ses droits transférables."""
    pair = compute_couple(person(interest_income=60_000), person(age=66, employment_income=20_000, rrif_income=2000),
                          options=options())
    donor, annex = pair.second.federal, pair.first.forms["5005-S2"]
    expected_100 = donor.amount("30800") + donor.amount("31200") + donor.amount("31205") + donor.amount("31260")
    assert donor.amount("100") == expected_100 == annex.amount("9")
    assert annex.amount("36100") == pytest.approx(max(0, donor.amount("26000") - 16129 - expected_100))
    assert annex.amount("13") == pytest.approx(11028 - annex.amount("36100"))
    assert_graph(pair)


def test_refus_transferts_et_symetrie():
    """Les choix sont respectés; inverser les personnes et le demandeur conserve leurs montants."""
    first, second = person(interest_income=50_000), person(age=66, rrif_income=10_000)
    on = compute_couple(first, second, options=options(spouse_amount_claimant="first", spouse_caregiver=False))
    reverse = compute_couple(second, first, options=options(spouse_amount_claimant="second", spouse_caregiver=False))
    assert on.first.to_dict() == reverse.second.to_dict()
    assert on.second.to_dict() == reverse.first.to_dict()
    off = compute_couple(first, second, options=options(federal_transfers=False, transfer_unused_quebec=False))
    assert "5005-S2" not in off.first.forms and "431" not in off.first.quebec.lines
    assert off.first.federal.amount("32600") == off.first.federal.amount("30300") == 0
    assert on.total_payable < off.total_payable


def test_transfert_quebec_et_imr():
    """Le transfert réduit de 100 % l’impôt ordinaire, mais de 50 % l’IMR dans ce cas."""
    first, second = person(capital_gains=600_000), person()
    pair = compute_couple(first, second, options=options())
    off = compute_couple(first, second, options=options(transfer_unused_quebec=False))
    a, b = pair.first, pair.second
    assert a.quebec.amount("431") == pytest.approx(2599.94)
    amt = a.forms["TP-776.42"]
    assert amt.amount("292") == pytest.approx(2599.94)
    assert amt.amount("257.1") == pytest.approx(1299.97)
    assert off.first.forms["TP-776.42"].amount("34") - amt.amount("34") == pytest.approx(1299.97)
    e = a.forms["TP-1.D.E"]
    assert e.amount("11") == a.quebec.amount("431")
    assert e.amount("12") == pytest.approx(max(0, a.quebec.amount("430") - a.quebec.amount("431")))
    assert b.quebec.amount("432") == 0
    assert_graph(pair)


def test_imr_transfert_dividendes_recalcule_plutot_que_moitie_du_solde():
    """Les crédits pour dividendes excédentaires du donneur ne gonflent pas le transfert IMR."""
    pair = compute_couple(person(capital_gains=600_000), person(eligible_dividends=25_000, rrsp_deduction=10_000), options=options())
    donor = pair.second.quebec
    amt = pair.first.forms["TP-776.42"]
    expected = max(0, donor.amount("399") - donor.amount("391") -
                   max(0, donor.amount("401") - donor.amount("391") - donor.amount("425")))
    assert amt.amount("292") == pytest.approx(expected)
    assert amt.amount("257.1") == pytest.approx(expected * 0.5)
    assert amt.amount("257.1") < pair.first.quebec.amount("431") * 0.5
    assert_graph(pair)


def test_questions_bloquantes_non_deduites_du_revenu():
    """Le statut québécois ne confirme ni le soutien du conjoint ni les transferts fédéraux."""
    a, b = person(interest_income=50_000), person()
    expected = {"options.spouse_amount_claimant", "options.federal_transfers"}
    assert set(required_couple_questions(a,b)) == expected
    with pytest.raises(MissingInformationError) as exc:
        compute_couple(a,b)
    assert set(exc.value.questions) == expected
    partial = options(spouse_amount_claimant="first")
    assert set(required_couple_questions(a,b,options=partial)) == {"options.spouse_caregiver"}
    assert required_couple_questions(a,b,options=options()) == {}


@pytest.mark.parametrize("values", ({"spouse_amount_claimant":"both"},{"spouse_amount_claimant":True},
    {"spouse_caregiver":1},{"federal_transfers":"yes"},{"transfer_unused_quebec":None},
    {"spouse_amount_claimant":"neither","spouse_caregiver":True}))
def test_options_invalides(values):
    """Aucune conversion silencieuse des réponses d’admissibilité."""
    with pytest.raises(ValueError):
        CoupleOptions(**values)


def test_solde_signe_du_tp1_sans_conjoint():
    """Le plancher n’intervient qu’à 432 : les montants négatifs officiels restent visibles."""
    result = compute(person(has_spouse=False))
    assert result.quebec.amount("413") == result.quebec.amount("430") == pytest.approx(-2599.94)
    assert result.quebec.amount("432") == 0 and "431" not in result.quebec.lines


def test_grille8_arret_si_credit_rajuste_nul():
    """La grille s’arrête à 292 si seuls des dividendes excédentaires étaient transférés."""
    donor = person(eligible_dividends=25_000, rrsp_deduction=10_000,
                   benefits=Benefits(workers_compensation=20_000, quebec_replacement_adjustment=18_571))
    pair = compute_couple(person(capital_gains=600_000), donor, options=options())
    assert pair.first.quebec.amount("431") > 0
    amt = pair.first.forms["TP-776.42"]
    assert amt.amount("292") == amt.amount("257.1") == 0
    assert "318" not in amt.lines
    assert_graph(pair)
