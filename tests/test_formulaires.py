# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Documents officiels, provenance, dépendances et compatibilité de la nouvelle API."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from profiles import single_public_taxpayer

from impotsqc import (Benefits, Deductions, PensionIncome, ChildSupportCase, Line, ParentIncome,
                      compute, compute_child_support)
from impotsqc.parameters import FORM_CODES, ParameterError, _check_forms, load_parameters

PROFILES = [
    {"age": 55, "pensions": (PensionIncome(30_000, "rpp"), PensionIncome(5_000, "rrsp_annuity", True))},
    {"age": 66, "interest_income": 150_000, "oas_pension": 8_000,
     "benefits": Benefits(federal_supplements=3_000, ei_regular=10_000, ei_repayment_exempt=False)},
    {"age": 55, "interest_income": 50_000,
     "benefits": Benefits(workers_compensation=30_000, quebec_replacement_adjustment=15_000,
                          social_assistance=5_000, quebec_social_assistance=4_000, ei_repaid=1_000)},
    {"age": 55, "employment_income": 30_000, "capital_gains": 600_000,
     "deductions": Deductions(rpp=5_000, union_dues_federal=1_150, union_dues_quebec=1_000)},
    {"age": 40},
    {"age": 40, "employment_income": 80_000},
    {"age": 66, "rrif_income": 30_000, "oas_pension": 9_000, "qpp_benefits": 12_000},
    {"age": 40, "lives_alone": True, "interest_income": 20_000},
    {"age": 67, "employment_income": 45_000},
    {"age": 65, "employment_income": 1_000},
    {"age": 64, "employment_income": 45_000},
    {"age": 60, "rrsp_income": 30_000},
    {"age": 50, "capital_gains": 600_000},
    {"age": 40, "employment_income": 350_000},
    {"age": 66, "rrif_income": 30_000, "eligible_dividends": 1_000, "other_dividends": 1_000,
     "capital_gains": 600_000, "employment_income": 20_000, "rrsp_deduction": 5_000},
]


@pytest.fixture(params=[(year, p) for year in (2025, 2026) for p in PROFILES])
def declaration(request):
    """Profils fictifs couvrant présence, absence et différents chemins des annexes."""
    year, profile = request.param
    return compute(single_public_taxpayer(year=year, **profile))


def test_metadonnees_et_alias(declaration):
    """Chaque document expose les métadonnées de l'année; les deux alias partagent leurs objets."""
    r = declaration
    metadata = load_parameters(r.taxpayer.year)["formulaires"]
    assert r.federal is r.forms["T1"] and r.quebec is r.forms["TP-1"]
    for code, form in r.forms.items():
        assert code in FORM_CODES and form.code == code and form.name == code
        assert form.title == metadata[code]["title"] and form.title
        assert form.version == metadata[code]["version"] and form.version
        assert form.source == metadata[code]["source"] and form.source.startswith("https://")
        assert all(n == line.number for n, line in form.lines.items())
    assert all(":" not in n for f in (r.federal, r.quebec) for n in f.lines)


def test_references_et_parametres_resolvent(declaration):
    """Aucun lien vers une ligne absente, aucun cycle, chaque paramètre possède sa source."""
    r = declaration
    params = load_parameters(r.taxpayer.year)
    graph = {}
    for code, form in r.forms.items():
        for number, line in form.lines.items():
            assert isinstance(line.refs, tuple) and isinstance(line.params, tuple)
            graph[f"{code}:{number}"] = line.refs
            for ref in line.refs:
                target, target_number = ref.split(":")
                assert target in r.forms and target_number in r.forms[target].lines, ref
            for key in line.params:
                file, table, field = key.split(".")
                assert field in params[file][table], key
                assert params[file][table]["source"].startswith("https://")
    visited = set()

    def visit(key, path):
        """Parcourt les dépendances pour détecter une circularité."""
        assert key not in path, (*path, key)
        if key not in visited:
            for target in graph[key]:
                visit(target, (*path, key))
            visited.add(key)

    for key in graph:
        visit(key, ())


def test_reports_des_annexes(declaration):
    """Les montants repris au TP-1 sont exactement ceux des lignes finales des annexes."""
    r = declaration
    for target, code, number in (("361", "TP-1.D.B", "34"), ("446", "TP-1.D.F", "82"),
                                  ("447", "TP-1.D.K", "98"), ("391", "TP-752.PC", "50")):
        if code in r.forms:
            assert r.quebec[target].amount == r.forms[code][number].amount
            assert r.quebec[target].refs == (f"{code}:{number}",)
        else:
            assert r.quebec[target].amount == 0 and r.quebec[target].refs == ()
    assert r.quebec["250"].amount == r.federal["23500"].amount
    assert r.quebec["250"].refs == ("T1:23500",)
    assert r.federal["30000"].params and r.quebec["350"].params


def test_json_correspond_aux_objets(declaration):
    """La sérialisation contient les documents complets, leurs lignes et les alias transitoires."""
    r = declaration
    d = json.loads(json.dumps(r.to_dict(), ensure_ascii=False))
    assert set(d) == {"year", "taxpayer", "forms", "federal", "quebec", "summary", "warnings"}
    assert d["year"] == r.taxpayer.year and set(d["forms"]) == set(r.forms)
    assert d["summary"]["total_payable"] == round(r.total_payable, 2)
    assert d["federal"] == d["forms"]["T1"]["lines"]
    assert d["quebec"] == d["forms"]["TP-1"]["lines"]
    for code, form in r.forms.items():
        doc = d["forms"][code]
        assert set(doc) == {"title", "version", "source", "lines"}
        assert (doc["title"], doc["version"], doc["source"]) == (form.title, form.version, form.source)
        assert set(doc["lines"]) == set(form.lines)
        for number, line in form.lines.items():
            assert doc["lines"][number] == {"label": line.label, "amount": round(line.amount, 2),
                                          "rule": line.rule, "refs": list(line.refs), "params": list(line.params)}


@pytest.mark.parametrize("year", (2025, 2026))
def test_formulaires_conditionnels(year):
    """Aucune annexe sans situation admissible; IMR au-delà de l'exemption, carrière dès 65 ans."""
    empty = compute(single_public_taxpayer(year=year, age=40))
    assert set(empty.forms) == {"T1", "TP-1"}
    salary = compute(single_public_taxpayer(year=year, age=40, employment_income=80_000))
    assert set(salary.forms) == {"T1", "TP-1", "TP-1.D.K", "5005-S8", "TP-1.D.U"}
    gain = compute(single_public_taxpayer(year=year, age=50, capital_gains=600_000))
    assert {"T691", "TP-776.42", "TP-1.D.E"} <= gain.forms.keys()
    assert gain.federal["41700"].refs == ("T1:40600", "T691:P1-103")
    assert gain.forms["T691"]["P6-14"].amount == gain.federal["41700"].amount
    assert gain.forms["TP-1.D.E"]["15"].amount == gain.forms["TP-776.42"]["34"].amount
    assert gain.forms["TP-1.D.E"]["18"].amount == gain.quebec["432"].amount
    p = load_parameters(year)
    for code, table in (("T691", "federal"), ("TP-776.42", "quebec")):
        exemption = p[table]["minimum_tax"]["exemption"]
        assert code not in compute(single_public_taxpayer(year=year, age=40, interest_income=exemption)).forms
        assert code in compute(single_public_taxpayer(year=year, age=40, interest_income=exemption + 1)).forms
    assert "TP-752.PC" not in compute(single_public_taxpayer(year=year, age=64, employment_income=45_000)).forms
    assert "TP-752.PC" in compute(single_public_taxpayer(year=year, age=65, employment_income=45_000)).forms
    assert "TP-752.PC" not in compute(single_public_taxpayer(year=year, age=65)).forms


@pytest.mark.parametrize("income, rate, extra", [(22_000, 0.0784, 0), (26_000, 0.1176, 392)])
def test_grille_annexe_k(income, rate, extra):
    """Les deux colonnes sans conjoint de l'annexe K 2025 sont lisibles ligne par ligne."""
    r = compute(single_public_taxpayer(year=2025, age=40, interest_income=income))
    k = r.forms["TP-1.D.K"]
    assert k["80"].amount == rate and k["82"].amount == extra
    assert k["81"].amount == k["79"].amount * rate
    assert k["83"].amount == k["81"].amount + k["82"].amount
    assert k["90"].amount == k["98"].amount == r.quebec["447"].amount


@pytest.mark.parametrize("year", (2025, 2026))
def test_fixation_pa_metadonnees(year):
    """Le formulaire de fixation utilise le même modèle et les métadonnées annuelles."""
    r = compute_child_support(ChildSupportCase(year=year, parent_a=ParentIncome(salary=90_000),
                              parent_b=ParentIncome(salary=60_000), custody_days_a=(100, 100)))
    metadata = load_parameters(year)["formulaires"]["FIXATION-PA"]
    assert r.form.code == "FIXATION-PA"
    assert (r.form.title, r.form.version, r.form.source) == (metadata["title"], metadata["version"], metadata["source"])
    d = json.loads(json.dumps(r.to_dict()))["form"]
    assert d["code"] == r.form.code and d["lines"]["603"]["amount"] == round(r.annual_amount, 2)


@pytest.mark.parametrize("key, value", [("title", ""), ("version", 2025), ("version", ""), ("source", "https://example.org/")])
def test_metadonnees_invalides_refusees(key, value):
    """Les champs propres aux documents sont validés, en plus du schéma commun des sources."""
    forms = deepcopy(load_parameters(2025)["formulaires"])
    forms["T1"][key] = value
    with pytest.raises(ParameterError):
        _check_forms(forms)


def test_formulaire_manquant_refuse():
    """Un catalogue incomplet est refusé au chargement."""
    forms = load_parameters(2025)["formulaires"]
    del forms["T691"]
    with pytest.raises(ParameterError, match="T691"):
        _check_forms(forms)


def test_ligne_immuable_et_resultats_independants():
    """L'extension de Line préserve l'immutabilité et chaque appel possède ses propres formulaires."""
    line = Line("1", "Essai", 10.0)
    assert line.refs == line.params == ()
    with pytest.raises(AttributeError):
        line.amount = 20.0
    a = compute(single_public_taxpayer(year=2025, age=40, employment_income=80_000))
    b = compute(a.taxpayer)
    a.federal.lines.clear()
    assert b.federal["10100"].amount == 80_000
    assert a.forms["TP-1.D.K"] is not b.forms["TP-1.D.K"]


@pytest.mark.parametrize("year", (2025, 2026))
@pytest.mark.parametrize("days", [(30, 30), (100, 100), (30, 330), (182.5, 182.5), (100, 300)])
def test_references_fixation_pa(year, days):
    """Les références de chaque section de garde restent à l'intérieur du formulaire rempli."""
    r = compute_child_support(ChildSupportCase(year=year, parent_a=ParentIncome(salary=90_000),
                              parent_b=ParentIncome(salary=60_000), custody_days_a=days, childcare=3_000))
    params = load_parameters(year)
    for line in r.form.lines.values():
        for ref in line.refs:
            code, number = ref.split(":")
            assert code == r.form.code and number in r.form.lines, ref
        for key in line.params:
            file, table, field = key.split(".")
            assert field in params[file][table], key
    assert r.form["301.A"].params == ("pension_alimentaire.basic_deduction.amount",)
    assert r.form["401"].refs == ("FIXATION-PA:306", "FIXATION-PA:400")
    assert r.form["603"].refs == ("FIXATION-PA:601", "FIXATION-PA:602")


def test_detail_des_etapes(declaration):
    """Les sous-totaux nouvellement exposés suivent les opérations des formulaires 2025."""
    r = declaration
    if "TP-1.D.B" in r.forms:
        b = r.forms["TP-1.D.B"]
        assert b["30"].amount == b["20"].amount + b["22"].amount + b["27"].amount
        assert b["34"].amount == max(0.0, b["30"].amount - b["31"].amount)
    if "TP-1.D.F" in r.forms:
        f = r.forms["TP-1.D.F"]
        assert f["36"].amount == pytest.approx(f["18"].amount - f["34"].amount, abs=1e-9)
        t = load_parameters(r.taxpayer.year)["quebec"]["health_services_fund"]
        maximum = t["first_maximum"] if f["70"].amount <= t["second_threshold"] else t["maximum"]
        assert f["82"].amount == min(f["80"].amount + f["81"].amount, maximum)
    if "T691" in r.forms:
        t = r.forms["T691"]
        assert t["P1-93"].amount == t["P1-83"].amount - t["P1-86"].amount
        assert t["P1-95"].amount == max(0.0, t["P1-93"].amount - t["P1-94"].amount)
        assert t["P1-103"].amount == max(0.0, t["P1-97"].amount - t["P1-102"].amount)
    if "TP-776.42" in r.forms:
        q = r.forms["TP-776.42"]
        assert q["22"].amount == q["18"].amount - q["19"].amount
        assert q["24"].amount == max(0.0, q["22"].amount - q["23"].amount)
        assert q["34"].amount == max(0.0, q["26"].amount - q["27"].amount)
