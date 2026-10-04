# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Propriétés du moteur : entrées validées, continuité, monotonie, routage des lignes, JSON."""

from __future__ import annotations

import json

import pytest

from impotsqc import Taxpayer, compute


def total(**kw) -> float:
    """Total à payer d'un contribuable 2026."""
    return compute(Taxpayer(year=2026, **kw)).total_payable


@pytest.mark.parametrize("kw", [{"age": 17}, {"age": 40, "employment_income": -1.0}, {"age": 40, "rrsp_income": -5.0}])
def test_entrees_invalides_refusees(kw):
    """Âge hors d'une vie adulte ou montant négatif : refus explicite."""
    with pytest.raises(ValueError):
        Taxpayer(year=2026, **kw)


def test_annee_absente():
    """Une année sans paramètres est refusée, avec la liste des années livrées."""
    with pytest.raises(ValueError, match="2026"):
        compute(Taxpayer(year=1999, age=40))


@pytest.mark.parametrize("seuil", [58_523, 117_045, 181_440, 258_482, 54_345 + 1_450, 95_323, 42_955])
def test_continuite_aux_seuils(seuil):
    """Aucun arrondi interne : l'impôt est continu de part et d'autre d'un seuil (retraiteqc en a
    besoin pour ses recherches de racine)."""
    a = total(age=72, rrif_income=seuil - 0.01, oas_pension=9_000)
    b = total(age=72, rrif_income=seuil + 0.01, oas_pension=9_000)
    assert 0 <= b - a < 0.02


def test_revenu_net_croissant():
    """Un dollar de plus retiré laisse toujours plus de revenu après impôt (taux marginal < 100 %) :
    c'est ce dont les recherches de racine de retraiteqc ont besoin.

    L'impôt, lui, n'est PAS monotone, et c'est le droit qui le veut : les premiers dollars de FERR
    ouvrent le montant pour revenu de pension (fédéral) et le montant pour revenus de retraite
    (Québec, 1,25 $ par dollar), qui valent plus que l'impôt sur ces dollars.
    """
    previous = total(age=72, rrif_income=0, oas_pension=9_000, qpp_benefits=20_000)
    baisses = 0
    for x in range(1_000, 300_001, 1_000):
        current = total(age=72, rrif_income=x, oas_pension=9_000, qpp_benefits=20_000)
        assert current - previous < 1_000
        baisses += current < previous
        previous = current
    assert baisses >= 1  # le premier millier de dollars de FERR réduit l'impôt total


def test_ferr_avant_65_ans():
    """Avant 65 ans, le FERR va à la ligne 13000 et n'ouvre pas le montant pour revenu de pension."""
    jeune = compute(Taxpayer(year=2026, age=60, rrif_income=20_000))
    vieux = compute(Taxpayer(year=2026, age=65, rrif_income=20_000))
    assert jeune.federal.amount("13000") == 20_000 and jeune.federal.amount("31400") == 0
    assert vieux.federal.amount("11500") == 20_000 and vieux.federal.amount("31400") == 2_000


def test_json_pour_agent():
    """`to_dict()` est sérialisable en JSON et porte lignes, résumé et avertissements."""
    r = compute(Taxpayer(year=2026, age=70, rrif_income=40_000, oas_pension=9_000, capital_gains=10_000))
    d = json.loads(json.dumps(r.to_dict(), ensure_ascii=False))
    assert d["federal"]["23600"]["label"] == "Revenu net"
    assert d["quebec"]["432"]["label"] == "Impôt du Québec"
    assert d["summary"]["total_payable"] == round(r.total_payable, 2)
    assert any("annexe K" in w for w in d["warnings"])


def test_credit_prolongation_de_carriere():
    """Ligne 391 : 14 % du revenu de travail au-delà de l'exclusion, plafonné; 65 ans et plus;
    réduit de 7 % du revenu net au-delà du seuil; limité à l'impôt qui reste après les autres crédits."""
    plein = compute(Taxpayer(year=2026, age=67, employment_income=45_000)).quebec
    assert plein.amount("391") == pytest.approx(0.14 * 12_755)
    borne = compute(Taxpayer(year=2026, age=67, employment_income=30_000)).quebec
    assert borne.amount("391") == pytest.approx(borne.amount("401") - borne.amount("377.1"))
    assert borne.amount("391") < 0.14 * 12_755 and borne.amount("432") == 0
    assert compute(Taxpayer(year=2026, age=64, employment_income=45_000)).quebec.amount("391") == 0
    reduit = compute(Taxpayer(year=2026, age=66, employment_income=70_000)).quebec
    attendu = 0.14 * 12_755 - 0.07 * (reduit.amount("275") - 57_660)
    assert reduit.amount("391") == pytest.approx(attendu) and 0 < attendu < 0.14 * 12_755
    assert compute(Taxpayer(year=2025, age=66, employment_income=95_000)).quebec.amount("391") == 0


def test_impot_minimum_gros_gain_en_capital():
    """Un gros gain en capital avec peu d'autres revenus déclenche l'IMR des deux côtés : le montant
    minimum remplace l'impôt ordinaire, l'abattement du Québec se calcule sur lui, et c'est signalé."""
    r = compute(Taxpayer(year=2026, age=50, capital_gains=600_000))
    f, q = r.federal, r.quebec
    assert f.amount("T691:103") > f.amount("40600") and f.amount("41700") == f.amount("T691:103")
    assert f.amount("44000") == pytest.approx(0.165 * f.amount("T691:103"))
    assert q.amount("E:15") > q.amount("430") and q.amount("432") == q.amount("E:15")
    assert any("minimum fédéral" in w for w in r.warnings) and any("minimum du Québec" in w for w in r.warnings)


def test_impot_minimum_sans_effet_sur_un_salarie():
    """Un salarié à revenu ordinaire n'est jamais touché : l'impôt ordinaire domine."""
    r = compute(Taxpayer(year=2026, age=40, employment_income=350_000))
    assert r.federal.amount("41700") == r.federal.amount("40600") and r.quebec.amount("432") == r.quebec.amount("430")
    assert not any("minimum" in w for w in r.warnings)
