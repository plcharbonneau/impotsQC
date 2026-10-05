# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Annexes 3, 8, G et U : numérotation officielle, reports et limites des entrées disponibles."""

import json

import pytest

from profiles import single_public_taxpayer

from impotsqc import compute
from impotsqc.parameters import load_parameters


@pytest.mark.parametrize("year", (2025, 2026))
@pytest.mark.parametrize("gain", (1, 20_000, 600_000))
def test_inclusion_et_reports_des_gains(year, gain):
    """Le total fourni reste distinct de l'inclusion; les deux déclarations reprennent leur annexe."""
    r = compute(single_public_taxpayer(year=year, age=40, capital_gains=gain))
    federal, quebec = r.forms["5000-S3"], r.forms["TP-1.D.G"]
    assert federal["19700"].amount == quebec["94.1"].amount == gain
    assert federal["23"].amount == quebec["107"].amount == 0.5
    assert federal["19900"].amount == quebec["108"].amount == gain / 2
    assert r.federal["12700"].amount == federal["19900"].amount
    assert r.quebec["139"].amount == quebec["108"].amount
    assert r.federal["12700"].refs == ("5000-S3:19900",)
    assert r.quebec["139"].refs == ("TP-1.D.G:108",)
    # Le gain agrégé ne permet pas d'inventer une catégorie d'actifs, un prix de base ou un produit.
    assert "13200" not in federal.lines and "10" not in quebec.lines
    assert set(federal.lines) == {"19700", "22", "23", "24", "19900"}
    assert set(quebec.lines) == {"94.1", "107", "107.1", "108"}


@pytest.mark.parametrize("year, salary, base, first, second", [
    (2025, 3_500, 0, 0, 0),
    (2025, 20_000, 891, 165, 0),
    (2025, 71_300, 3_661.20, 678, 0),
    (2025, 80_000, 3_661.20, 678, 348),
    (2025, 81_200, 3_661.20, 678, 396),
    (2025, 120_000, 3_661.20, 678, 396),
    (2026, 3_500, 0, 0, 0),
    (2026, 20_000, 874.50, 165, 0),
    (2026, 74_600, 3_768.30, 711, 0),
    (2026, 80_000, 3_768.30, 711, 216),
    (2026, 85_000, 3_768.30, 711, 416),
    (2026, 120_000, 3_768.30, 711, 416),
])
def test_rrq_composantes_et_reports(year, salary, base, first, second):
    """Cotisations indépendamment chiffrées, y compris les deux plafonds, pour chaque année."""
    r = compute(single_public_taxpayer(year=year, age=40, employment_income=salary))
    s8 = r.forms["5005-S8"]
    assert s8["P1-A"].amount == 12
    assert s8["P2-11"].amount == pytest.approx(base)
    assert s8["P2-12"].amount == pytest.approx(first)
    assert s8["P2-22"].amount == pytest.approx(second)
    assert s8["P2-24"].amount == 0
    assert r.federal["30800"].amount == s8["P2-35"].amount
    assert r.federal["22215"].amount == s8["P2-47"].amount
    assert r.federal["30800"].refs == ("5005-S8:P2-35",)
    assert r.federal["22215"].refs == ("5005-S8:P2-47",)
    assert r.quebec["98.1"].amount == min(salary, s8["P1-D"].amount)
    if first:
        u = r.forms["TP-1.D.U"]
        assert u["16"].amount == pytest.approx(first)
        assert u["22"].amount == pytest.approx(second)
        assert r.quebec["248"].amount == u["23"].amount == s8["P2-47"].amount
        assert r.quebec["248"].refs == ("TP-1.D.U:23",)
        assert u["23"].amount == u["22"].amount + u["22.1"].amount
        assert u["12"].amount == min(salary, s8["P1-B"].amount)
        assert u["18.5"].amount == min(salary, s8["P1-D"].amount)
    else:
        assert "TP-1.D.U" not in r.forms and r.quebec["248"].amount == 0


@pytest.mark.parametrize("year", (2025, 2026))
@pytest.mark.parametrize("salary", (0, 1, 3_500, 3_500.01))
def test_presence_selon_salaire(year, salary):
    """L'annexe 8 suit le revenu d'emploi; U suit la déduction; les gains n'inventent pas de revenu."""
    r = compute(single_public_taxpayer(year=year, age=40, employment_income=salary))
    assert ("5005-S8" in r.forms) == (salary > 0)
    assert ("TP-1.D.U" in r.forms) == (salary > 3_500)
    assert "5000-S3" not in r.forms and "TP-1.D.G" not in r.forms
    assert "5005-S10" not in r.forms and "TP-1.D.R" not in r.forms


@pytest.mark.parametrize("age, expected", [(18, False), (19, True), (64, True), (65, True), (72, True), (73, False), (80, False)])
def test_limites_age_rrq(age, expected):
    """Les âges dont la règle historique est incomplète sont signalés, sans changer leurs montants."""
    r = compute(single_public_taxpayer(year=2025, age=age, employment_income=80_000))
    assert ("5005-S8" in r.forms) == expected
    assert ("TP-1.D.U" in r.forms) == expected
    assert r.federal["30800"].amount == pytest.approx(3_661.20)
    assert r.federal["22215"].amount == r.quebec["248"].amount == 1_026
    assert any("annexes 8 et U non produites" in warning for warning in r.warnings) == (not expected)
    if not expected:
        assert r.federal["22215"].refs == r.quebec["248"].refs == ()


@pytest.mark.parametrize("year", (2025, 2026))
def test_json_et_provenance_du_profil_mixte(year):
    """Les quatre nouveaux documents se lisent dans le JSON; les liens et paramètres se résolvent."""
    r = compute(single_public_taxpayer(year=year, age=40, employment_income=80_000, capital_gains=20_000))
    data = json.loads(json.dumps(r.to_dict()))
    params = load_parameters(year)
    for code in ("5000-S3", "5005-S8", "TP-1.D.G", "TP-1.D.U"):
        f = r.forms[code]
        assert f.code == code and f.title and f.version
        assert f.source.startswith("https://") and f.source.endswith(".pdf")
        assert set(data["forms"][code]["lines"]) == set(f.lines)
        assert data["forms"][code]["source"] == f.source
        assert params["formulaires"][code]["status"] == ("published" if year == 2025 else "rule_2025")
        for line in f.lines.values():
            assert isinstance(line.amount, float)
            for ref in line.refs:
                target, number = ref.split(":")
                assert number in r.forms[target].lines
            for key in line.params:
                file, table, field = key.split(".")
                assert field in params[file][table] and params[file][table]["source"].startswith("https://")
