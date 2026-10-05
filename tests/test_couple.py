# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Coordination familiale et partage de B : cas officiels chiffrés et graphe des dépendances."""

from dataclasses import replace
import json

import pytest

from impotsqc import (Form, MissingInformationError, Taxpayer, compute, compute_couple,
                      required_couple_questions)
from test_formulaires import (test_metadonnees_et_alias as check_metadata,
                              test_references_et_parametres_resolvent as check_local_refs,
                              test_json_correspond_aux_objets as check_json,
                              test_reports_des_annexes as check_annexes)


def person(**values):
    """Profil fictif avec couverture privée annuelle et statut de conjoint confirmé."""
    return Taxpayer(**(dict(year=2025, age=66, has_spouse=True,
                           drug_plan_exempt_months=tuple(range(1, 13))) | values))


@pytest.mark.parametrize("share", (0, 0.1, 0.25, 0.5, 0.75, 1))
def test_reduction_familiale_unique_et_partage(share):
    """Annexe B 2025 : deux droits d’âge et de pension, une seule réduction sur 50 000 $."""
    pair = compute_couple(person(rrif_income=25_000), person(rrif_income=25_000),
                          schedule_b_first_share=share)
    # Source : B 2025, lignes 22/23, 27/28, 16 et 31. Aucun appel à la règle testée.
    total = 2 * 3_906 + 2 * 3_470 - (50_000 - 42_090) * 0.1875
    a, b = pair.first.forms["TP-1.D.B"], pair.second.forms["TP-1.D.B"]
    assert a.amount("30") == b.amount("30") == 14_752
    assert a.amount("31") == b.amount("31") == 1_483.125
    assert a.amount("32") == b.amount("32") == total
    assert a.amount("34") == pytest.approx(total * share)
    assert b.amount("34") == pytest.approx(total * (1 - share))
    assert a.amount("33") == pytest.approx(b.amount("34"))
    assert b.amount("33") == pytest.approx(a.amount("34"))
    assert a.amount("34") + b.amount("34") == pytest.approx(total)
    assert pair.first.quebec.amount("361") == a.amount("34")
    assert pair.second.quebec.amount("361") == b.amount("34")


def test_droits_du_conjoint_sans_droits_personnels():
    """Le conjoint plus jeune peut demander tout le montant commun selon le choix déclaré."""
    pair = compute_couple(person(age=40), person(rrif_income=5_000), schedule_b_first_share=1)
    a = pair.first.forms["TP-1.D.B"]
    assert a.amount("22") == a.amount("27") == 0
    assert a.amount("23") == 3_906 and a.amount("28") == 3_470
    assert a.amount("34") == 7_376 and pair.second.quebec.amount("361") == 0
    assert "1" not in a.lines and a.amount("1.C") == 5_000


@pytest.mark.parametrize("first_alone,second_alone", ((True, False), (False, True), (True, True)))
def test_vivre_seul_admissible_separation_involontaire(first_alone, second_alone):
    """Le guide 361 exige le même total pour personne vivant seule dans les deux annexes."""
    pair = compute_couple(person(age=40, lives_alone=first_alone),
                          person(age=40, lives_alone=second_alone))
    amount = 2_128 * (first_alone + second_alone)
    assert pair.first.forms["TP-1.D.B"].amount("20") == amount
    assert pair.second.forms["TP-1.D.B"].amount("20") == amount
    assert pair.first.quebec.amount("361") + pair.second.quebec.amount("361") == amount


@pytest.mark.parametrize("year", (2025, 2026))
def test_revenus_calcule_ramq_symetrie_et_documents(year):
    """Le revenu du conjoint vient du TP-1; l’inversion des personnes conserve leurs résultats."""
    first = person(year=year, age=67, employment_income=30_000, rrif_income=10_000,
                   drug_plan_exempt_months=(), drug_plan_dependent_children=0)
    second = person(year=year, age=40, employment_income=15_000,
                    drug_plan_exempt_months=(1, 2, 3, 4, 5, 6), drug_plan_dependent_children=0)
    pair = compute_couple(first, second, schedule_b_first_share=0.75)
    swapped = compute_couple(second, first, schedule_b_first_share=0.25)
    assert first.spouse_net_income is second.spouse_net_income is None
    assert pair.first.taxpayer.spouse_net_income == pair.second.quebec.amount("275")
    assert pair.second.taxpayer.spouse_net_income == pair.first.quebec.amount("275")
    for result, reverse in ((pair.first, swapped.second), (pair.second, swapped.first)):
        assert result.to_dict() == reverse.to_dict()
        separate = compute(result.taxpayer)
        assert result.federal.to_dict() == separate.federal.to_dict()
        assert result.quebec.amount("447") == separate.quebec.amount("447")
        assert any("reste incomplet" in w for w in result.warnings)
        assert not any("seulement vos montants" in w for w in result.warnings)
        check_metadata(result)
        check_local_refs(result)
        check_json(result)
        check_annexes(result)
    assert pair.refs["first/TP-1.D.K:37"] == ("second/TP-1:275",)
    assert pair.refs["second/TP-1.D.B:1.C"] == ("first/TP-1:122",)
    data = json.loads(json.dumps(pair.to_dict(), ensure_ascii=False))
    assert data["first"] == json.loads(json.dumps(pair.first.to_dict()))
    assert data["second"] == json.loads(json.dumps(pair.second.to_dict()))
    assert data["summary"]["total_payable"] == round(pair.first.total_payable + pair.second.total_payable, 2)


def test_graphe_familial_sans_cycle():
    """Tous les liens locaux et interpersonnels se résolvent sans cycle de crédit partagé."""
    pair = compute_couple(person(rrif_income=20_000), person(rrif_income=30_000))
    graph = {}
    for name, result in (("first", pair.first), ("second", pair.second)):
        for code, form in result.forms.items():
            for number, line in form.lines.items():
                key = f"{name}/{code}:{number}"
                graph[key] = tuple(f"{name}/{ref}" for ref in line.refs) + pair.refs.get(key, ())
    for source, targets in pair.refs.items():
        assert source in graph
        for target in targets:
            assert target in graph
    visited = set()

    def visit(node, path):
        """Parcours des dépendances avec détection des boucles."""
        assert node not in path
        if node not in visited:
            for target in graph[node]:
                visit(target, path + (node,))
            visited.add(node)

    for node in graph:
        visit(node, ())


def test_pas_de_formulaire_inutile(monkeypatch):
    """Chaque document n’est construit qu’une fois par personne; pas de déclaration provisoire."""
    created = []
    original = Form.from_parameters

    def create(cls, code, params):
        """Compte les documents réellement créés sans remplacer leur calcul."""
        created.append(code)
        return original(code, params)

    monkeypatch.setattr(Form, "from_parameters", classmethod(create))
    pair = compute_couple(person(rrif_income=25_000), person(rrif_income=25_000))
    assert sorted(created) == sorted(tuple(pair.first.forms) + tuple(pair.second.forms))
    assert len(created) == len(pair.first.forms) + len(pair.second.forms)
    young = compute_couple(person(age=40), person(age=40))
    assert set(young.first.forms) == set(young.second.forms) == {"T1", "TP-1"}


def test_questions_identifient_la_personne_sans_redemander_le_revenu():
    """Les questions RAMQ et le statut restent bloquants; le revenu du conjoint est dérivé."""
    first = Taxpayer(year=2025, age=40)
    second = person(age=40)
    expected = {"first.has_spouse", "first.drug_plan_exempt_months", "first.drug_plan_dependent_children"}
    assert set(required_couple_questions(first, second)) == expected
    with pytest.raises(MissingInformationError) as exc:
        compute_couple(first, second)
    assert set(exc.value.questions) == expected
    assert required_couple_questions(person(), person()) == {}


@pytest.mark.parametrize("share", (-0.1, 1.1, float("inf"), float("nan"), True, None, "0.5"))
def test_partage_invalide_refuse(share):
    """Un choix de partage incohérent ne produit aucun calcul présumé."""
    with pytest.raises(ValueError, match="schedule_b_first_share"):
        compute_couple(person(), person(), schedule_b_first_share=share)


@pytest.mark.parametrize("first,second,match", (
    (person(), person(year=2026), "même année"),
    (person(has_spouse=False), person(), "has_spouse=False"),
    (person(spouse_net_income=10_000), person(), "spouse_net_income"),
))
def test_menage_incoherent_refuse(first, second, match):
    """Année, statut et revenu fourni doivent être cohérents avec les déclarations."""
    with pytest.raises(ValueError, match=match):
        compute_couple(first, second)


def test_revenu_fourni_arrondi_au_cent_accepte():
    """Une valeur saisie au cent est vérifiée puis remplacée par le calcul non arrondi."""
    second = person(age=40, employment_income=12_345.67)
    standalone = compute(replace(second, spouse_net_income=0))
    first = person(age=40, spouse_net_income=round(standalone.quebec.amount("275"), 2))
    pair = compute_couple(first, second)
    assert pair.first.taxpayer.spouse_net_income == pair.second.quebec.amount("275")


@pytest.mark.parametrize("income", (42_089, 42_090, 42_091, 80_000, 600_000))
def test_seuils_famille_et_impot_minimum(income):
    """Les frontières de B restent continues et les formulaires IMR restent raccordés."""
    pair = compute_couple(person(interest_income=income), person(rrif_income=5_000))
    expected = max(0.0, 2 * 3_906 + 3_470 - max(0.0, income + 5_000 - 42_090) * 0.1875)
    assert pair.first.quebec.amount("361") + pair.second.quebec.amount("361") == pytest.approx(expected)
    for result in (pair.first, pair.second):
        check_local_refs(result)
        check_annexes(result)
