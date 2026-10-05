# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Annexe K : réponses obligatoires, mois exemptés et situation familiale explicite.

Cas chiffrés : annexe K 2025, parties A à C (lignes 36 à 98). Les enfants désignent ici
les enfants admissibles au sens de l'annexe, et les mois désignent des exemptions confirmées.
"""

import json
from dataclasses import replace

import pytest

from impotsqc import MissingInformationError, Taxpayer, compute, load_parameters, required_questions, rules


@pytest.fixture
def taxpayer():
    """Personne fictive sans conjoint ni enfant, sans mois exempté, année publiée 2025."""
    return Taxpayer(year=2025, age=40, interest_income=25_000, has_spouse=False,
                    drug_plan_exempt_months=(), drug_plan_dependent_children=0)


@pytest.mark.parametrize("profile", [{}, {"age": 70}, {"lives_alone": True}, {"employment_income": 80_000}])
def test_renseignements_inconnus_bloquent_le_calcul(profile, monkeypatch):
    """L'âge, l'emploi et le fait de vivre seul ne permettent d'inférer ni conjoint ni assurance."""
    def unexpected(*args, **kwargs):
        """Échoue si le moteur a commencé le calcul des impôts malgré les renseignements manquants."""
        pytest.fail("le calcul ne doit pas commencer")

    monkeypatch.setattr("impotsqc.federal_return", unexpected)
    tp = Taxpayer(**dict(year=2025, age=40) | profile)
    questions = required_questions(tp)
    assert set(questions) == {"has_spouse", "drug_plan_exempt_months", "drug_plan_dependent_children"}
    assert all(isinstance(q, str) and q for q in questions.values())
    assert "31 décembre 2025" in questions["has_spouse"]
    with pytest.raises(MissingInformationError) as exc:
        compute(tp)
    assert exc.value.questions == questions
    assert json.loads(json.dumps(exc.value.to_dict())) == {"error": "missing_information", "questions": questions}


def test_questions_conditionnelles_et_revenu_conjoint_nul(taxpayer):
    """Le revenu du conjoint est demandé même s'il vaut zéro; une couverture privée suffit sans enfants."""
    couple = replace(taxpayer, has_spouse=True)
    assert set(required_questions(couple)) == {"spouse_net_income"}
    with pytest.raises(MissingInformationError):
        compute(couple)
    assert required_questions(replace(couple, spouse_net_income=0)) == {}
    private = replace(taxpayer, drug_plan_exempt_months=tuple(range(1, 13)), drug_plan_dependent_children=None)
    assert required_questions(private) == {}
    assert compute(private).quebec.amount("447") == 0
    assert set(required_questions(replace(private, has_spouse=None))) == {"has_spouse"}


@pytest.mark.parametrize("field,value", [
    ("has_spouse", 0), ("has_spouse", "single"),
    ("drug_plan_exempt_months", 12), ("drug_plan_exempt_months", "1,2"),
    ("drug_plan_exempt_months", (0,)), ("drug_plan_exempt_months", (13,)),
    ("drug_plan_exempt_months", (1, 1)), ("drug_plan_exempt_months", (True,)),
    ("drug_plan_exempt_months", (1.0,)),
    ("drug_plan_dependent_children", -1), ("drug_plan_dependent_children", 1.5),
    ("drug_plan_dependent_children", True),
    ("spouse_net_income", -1), ("spouse_net_income", float("nan")),
    ("spouse_net_income", float("inf")), ("spouse_net_income", "10000"), ("spouse_net_income", True),
])
def test_reponses_invalides_refusees(taxpayer, field, value):
    """Les réponses ne sont pas coercées silencieusement et les mois ne sont jamais comptés deux fois."""
    with pytest.raises(ValueError, match=field):
        replace(taxpayer, **({"has_spouse": True} | {field: value}))


def test_revenu_conjoint_incompatible_et_liste_json(taxpayer):
    """Pas de revenu conjoint sans conjoint; une liste JSON de mois est copiée en tuple immuable."""
    with pytest.raises(ValueError, match="spouse_net_income"):
        replace(taxpayer, spouse_net_income=0)
    months = [12, 1, 6]
    tp = replace(taxpayer, drug_plan_exempt_months=months)
    months.append(2)
    assert tp.drug_plan_exempt_months == (1, 6, 12)
    d = json.loads(json.dumps(compute(tp).to_dict()))
    assert d["taxpayer"]["drug_plan_exempt_months"] == [1, 6, 12]
    assert Taxpayer(**d["taxpayer"]) == tp


@pytest.mark.parametrize("exempt, expected", [
    ((), 755.0),
    (tuple(range(1, 13)), 0.0),
    (tuple(range(1, 7)), 383.0),
    (tuple(range(7, 13)), 372.02),
    ((1,), 693.0),
    ((12,), 691.17),
])
def test_plafonds_et_mois_exemptes_2025(taxpayer, exempt, expected):
    """À haut revenu : plafonds officiels 766, 755, 62 et 63,83 $, pas un simple prorata de 755 $."""
    r = compute(replace(taxpayer, interest_income=80_000, drug_plan_exempt_months=exempt))
    assert r.quebec.amount("447") == pytest.approx(expected)
    if len(exempt) == 12:
        assert "TP-1.D.K" not in r.forms
    else:
        k = r.forms["TP-1.D.K"]
        assert k.amount("60") == sum(m <= 6 for m in exempt)
        assert k.amount("61") == sum(m > 6 for m in exempt)
        assert k.amount("62") == len(exempt)
        assert k.amount("85") == pytest.approx(766 * len(exempt) / 12)
        assert k.amount("88") == pytest.approx(k.amount("60") * 62 + k.amount("61") * 63.83)
        assert k.amount("90") == k.amount("98") == r.quebec.amount("447")


def test_prorata_selon_le_revenu_et_impots_inchanges(taxpayer):
    """À revenu modéré, la réduction porte sur la cotisation calculée, et seul le TP-1 447/450 bouge."""
    full = compute(taxpayer)
    partial = compute(replace(taxpayer, drug_plan_exempt_months=(1, 2, 3)))
    private = compute(replace(taxpayer, drug_plan_exempt_months=tuple(range(1, 13))))
    # (25 000 - 19 890 - 5 000) × 11,76 % + 392 = 404,936 $
    assert full.quebec.amount("447") == pytest.approx(404.936)
    assert partial.quebec.amount("447") == pytest.approx(303.702)
    for r in (partial, private):
        assert r.federal.lines == full.federal.lines
        for number, line in full.quebec.lines.items():
            if number not in ("447", "450"):
                assert r.quebec[number] == line
        assert full.total_payable - r.total_payable == pytest.approx(404.936 - r.quebec.amount("447"))


@pytest.mark.parametrize("spouse_income, expected, rate", [(0, 0, None), (12_000, 187.068, .0393),
                                                         (20_000, 653.564, .0589), (80_000, 755, None)])
def test_bareme_couple_et_revenu_familial(taxpayer, spouse_income, expected, rate):
    """Les deux colonnes avec conjoint utilisent le revenu net combiné, sans doubler la prime personnelle."""
    tp = replace(taxpayer, has_spouse=True, spouse_net_income=spouse_income)
    r = compute(tp)
    assert r.quebec.amount("447") == pytest.approx(expected)
    if "TP-1.D.K" in r.forms:
        k = r.forms["TP-1.D.K"]
        assert k.amount("37") == spouse_income
        assert k.amount("40") == 25_000 + spouse_income
        assert k.amount("41") == 32_240
        if rate:
            assert k.amount("80") == rate
        assert k.amount("98") == k.amount("90")
        assert "97" not in k.lines
    assert any("Couple" in w and "transferts" in w for w in r.warnings)


@pytest.mark.parametrize("has_spouse, children, exemption", [
    (False, 0, 19_890), (False, 1, 32_240), (False, 2, 36_460), (False, 3, 36_460),
    (True, 0, 32_240), (True, 1, 36_460), (True, 2, 40_360), (True, 3, 40_360),
])
def test_exemptions_et_seuils_familiaux(taxpayer, has_spouse, children, exemption):
    """Les lignes 41, 42 et 44 portent les exemptions officielles selon la composition familiale."""
    spouse_income = 10_000 if has_spouse else None
    tp = replace(taxpayer, has_spouse=has_spouse, spouse_net_income=spouse_income,
                 drug_plan_dependent_children=children, interest_income=exemption - (spouse_income or 0))
    assert compute(tp).quebec.amount("447") == 0
    over = compute(replace(tp, interest_income=tp.interest_income + 1))
    k = over.forms["TP-1.D.K"]
    assert k.amount("46") == exemption
    assert k.amount("48") == 1
    assert k.amount("90") == pytest.approx(.0393 if has_spouse else .0784)
    if children:
        number = "42" if has_spouse else "44"
        assert k.amount(number) == exemption - k.amount("41")
        assert k[number].params


def test_statut_fiscal_distinct_de_vivre_seul(taxpayer):
    """Vivre seul change l'annexe B, sans choisir le barème RAMQ ni imposer un statut de couple."""
    for spouse_income in (None, 15_000):
        tp = replace(taxpayer, has_spouse=spouse_income is not None, spouse_net_income=spouse_income)
        assert compute(tp).quebec.amount("447") == compute(replace(tp, lives_alone=True)).quebec.amount("447")


def test_revenu_net_utilise_et_annexe_b_avertie(taxpayer):
    """Le revenu brut n'est pas utilisé; le conjoint entre aussi dans la réduction de l'annexe B."""
    tp = replace(taxpayer, age=66, interest_income=0, employment_income=30_000,
                 has_spouse=True, spouse_net_income=30_000)
    r = compute(tp)
    family = r.quebec.amount("275") + 30_000
    assert family < 60_000
    assert r.forms["TP-1.D.K"].amount("40") == family
    assert r.forms["TP-1.D.B"].amount("12") == 30_000
    assert r.forms["TP-1.D.B"].amount("14") == family
    assert r.forms["TP-1.D.B"].amount("31") == pytest.approx((family - 42_090) * .1875)
    assert any("droits du conjoint" in w for w in r.warnings)


@pytest.mark.parametrize("year", [2025, 2026])
@pytest.mark.parametrize("has_spouse", [False, True])
def test_regle_et_annexe_mois_references_et_continuite(taxpayer, year, has_spouse):
    """Tous les comptes semestriels : calcul borné, références valides et revenu après impôt croissant."""
    table = load_parameters(year)["quebec"]["drug_insurance"]
    params = load_parameters(year)
    tp = replace(taxpayer, year=year, has_spouse=has_spouse, spouse_net_income=10_000 if has_spouse else None)
    for first in range(7):
        for second in range(7):
            months = tuple(range(1, first + 1)) + tuple(range(7, 7 + second))
            tp = replace(tp, drug_plan_exempt_months=months)
            for income in (25_000, 40_000, 80_000):
                r = compute(replace(tp, interest_income=income))
                expected = rules.drug_insurance_premium(income + (tp.spouse_net_income or 0), table,
                                                        has_spouse=has_spouse, dependent_children=0,
                                                        exempt_months=months)
                assert r.quebec.amount("447") == pytest.approx(expected)
                assert 0 <= expected <= table["annual_maximum"]
                for form in r.forms.values():
                    for line in form.lines.values():
                        for ref in line.refs:
                            code, number = ref.split(":")
                            assert number in r.forms[code].lines
                        for key in line.params:
                            file, group, parameter = key.split(".")
                            assert parameter in params[file][group]
                d = json.loads(json.dumps(r.to_dict()))
                assert d["forms"] == {code: form.to_dict() for code, form in r.forms.items()}
    status = "couple" if has_spouse else "single"
    exemption = table[f"exemption_{status}"]
    rate = table[f"second_rate_{status}"]
    width = table["first_bracket_width"]
    base = width * table[f"first_rate_{status}"]
    thresholds = (exemption, exemption + width, exemption + width + (table["rate_cap"] - base) / rate,
                  exemption + width + (table["annual_maximum"] - base) / rate)
    for threshold in thresholds:
        income = threshold - (tp.spouse_net_income or 0)
        tp = replace(tp, drug_plan_exempt_months=(1, 7))
        a = compute(replace(tp, interest_income=income - .01))
        b = compute(replace(tp, interest_income=income + .01))
        assert 0 <= b.total_payable - a.total_payable < .02


def test_parametres_2026_provisoires_meme_si_exemption(taxpayer):
    """Une exemption 2026 estimée doit aussi porter un avertissement, sauf couverture privée complète."""
    r = compute(replace(taxpayer, year=2026, has_spouse=True, spouse_net_income=0))
    assert r.quebec.amount("447") == 0
    assert any("annexe K" in w and "provisoires" in w for w in r.warnings)
    private = compute(replace(taxpayer, year=2026, drug_plan_exempt_months=tuple(range(1, 13))))
    assert not any("annexe K" in w for w in private.warnings)
