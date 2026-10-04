# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Modèle québécois de fixation des pensions alimentaires pour enfants.

Les exemples chiffrés viennent du guide officiel « Le modèle québécois de fixation des pensions
alimentaires pour enfants » (ministère de la Justice), calculés avec la table de 2018 : revenus
disponibles de 44 000 $ et 36 000 $ (déduction de base de 11 155 $), 2 enfants, contribution de
base de 14 090 $, frais de garde nets de 2 000 $.
"""

from __future__ import annotations

import pytest

from impotsqc import Taxpayer, compute
from impotsqc.child_support import (ChildSupportCase, ParentIncome, _classify, _section4, base_contribution,
                                    compute_child_support)
from impotsqc.model import Form
from impotsqc.parameters import load_parameters

GUIDE = {"pension_alimentaire": {
    "basic_deduction": {"amount": 11_155},
    "base_contribution_table": {
        "upper_bounds": [78_000, 80_000, 200_000],
        "amounts_1_child": [9_670, 9_800, 14_350], "amounts_2_children": [13_900, 14_090, 19_860],
        "amounts_3_children": [17_730, 17_990, 26_360], "amounts_4_children": [21_580, 21_880, 32_270],
        "amounts_5_children": [25_400, 25_780, 38_770], "amounts_6_children": [29_230, 29_670, 44_670],
        "excess_over": 200_000, "excess_rates_by_children": [0.035, 0.045, 0.065, 0.08, 0.10, 0.115]}}}
PERE, MERE = ParentIncome(salary=55_155), ParentIncome(salary=47_155)


def guide(days_pere, **frais):
    """Cas du guide (parent A = père), selon les jours passés avec le père pour chaque enfant."""
    case = ChildSupportCase(year=2018, parent_a=PERE, parent_b=MERE, custody_days_a=days_pere, **frais)
    return compute_child_support(case, params=GUIDE)


def test_guide_revenu_disponible_et_contribution():
    """Parties 3 et 4 : 44 000 $ et 36 000 $, 55 % et 45 %, contribution de base de 14 090 $."""
    f = guide((0, 0)).form
    assert (f.amount("305.A"), f.amount("305.B"), f.amount("306")) == (44_000, 36_000, 80_000)
    assert f.amount("307.A") == pytest.approx(0.55) and f.amount("401") == 14_090
    assert f.amount("402.A") == pytest.approx(7_749.50) and f.amount("402.B") == pytest.approx(6_340.50)


def test_guide_section_1_garde_exclusive():
    """Garde exclusive à la mère : le père paie 55 % × (14 090 $ + 2 000 $) = 8 849,50 $."""
    r = guide((30, 30), childcare=2_000)
    assert (r.section, r.payer) == ("1", "A") and r.annual_amount == pytest.approx(8_849.50)


def test_guide_section_1_1_droit_de_visite_prolonge():
    """Père 26 % du temps : compensation de 6 % × 14 090 $ = 845,40 $; pension de 8 384,53 $."""
    r = guide((0.26 * 365, 0.26 * 365), childcare=2_000)
    assert r.section == "1.1" and r.form.amount("516") == pytest.approx(845.40)
    assert r.annual_amount == pytest.approx(8_384.53, abs=0.01)


def test_guide_section_3_garde_partagee():
    """Garde partagée 50/50 : le père remet 704,50 $ plus sa part des frais (1 100 $) = 1 804,50 $."""
    r = guide((182.5, 182.5), childcare=2_000)
    assert r.section == "3" and r.form.amount("533.A") == pytest.approx(704.50)
    assert (r.payer, r.annual_amount) == ("A", pytest.approx(1_804.50)) and r.form.amount("534.B") == 0


@pytest.mark.parametrize("days", [(30, 30), (0.26 * 365, 0.26 * 365), (30, 330), (182.5, 182.5), (100, 300)])
def test_section_4_generalise_les_autres(days):
    """La section 4 donne la même pension que les sections 1, 1.1, 2 et 3 dans leurs cas."""
    r = guide(days, childcare=2_000)
    p = GUIDE["pension_alimentaire"]
    f = Form("essai")
    factor = {"A": r.form.amount("307.A"), "B": r.form.amount("307.B")}
    payable = _section4(f, _classify(days), r.form.amount("401"), len(days), factor,
                        {"A": r.form.amount("407.A"), "B": r.form.amount("407.B")}, {"A": 0.0, "B": 0.0})
    assert payable[r.payer] == pytest.approx(r.form.amount("602") if r.payer else 0.0)


def test_section_2_un_enfant_chez_chaque_parent():
    """Un enfant chez chaque parent : le parent au revenu le plus élevé paie l'écart."""
    r = guide((330, 30), childcare=0)
    assert r.section == "2" and r.payer == "A"
    assert r.annual_amount == pytest.approx(14_090 * 0.55 - 14_090 / 2)


def test_classement_des_seuils():
    """20 % et moins : exclusive; entre 20 % et 40 % : prolongé; au moins 40 % chacun : partagée."""
    assert [k for k, _, _ in _classify((73, 74, 146, 182.5, 219, 292, 365))] == [
        "exclusive", "extended", "shared", "shared", "shared", "exclusive", "exclusive"]


def test_tables_officielles_2025_2026():
    """Tables officielles : lecture par tranche, excédent au-delà de 200 000 $, plus de 6 enfants."""
    t = load_parameters(2026)["pension_alimentaire"]["base_contribution_table"]
    assert base_contribution(80_000, 2, t) == (t["amounts_2_children"][t["upper_bounds"].index(80_000)], False)
    assert base_contribution(80_000.5, 2, t)[0] == t["amounts_2_children"][t["upper_bounds"].index(82_000)]
    haut, au_dela = base_contribution(250_000, 1, t)
    assert au_dela and haut == pytest.approx(t["amounts_1_child"][-1] + 0.035 * 50_000)
    six, cinq = base_contribution(90_000, 6, t)[0], base_contribution(90_000, 5, t)[0]
    assert base_contribution(90_000, 8, t)[0] == pytest.approx(six + 2 * (six - cinq))
    assert load_parameters(2025)["pension_alimentaire"]["basic_deduction"]["amount"] == 13_575
    assert load_parameters(2026)["pension_alimentaire"]["basic_deduction"]["amount"] == 13_865


def test_capacite_de_payer():
    """Partie 6 : la pension ne dépasse pas 50 % du revenu disponible du débiteur."""
    case = ChildSupportCase(year=2026, parent_a=ParentIncome(salary=20_000), parent_b=ParentIncome(),
                            custody_days_a=(0, 0, 0), special_expenses=40_000)
    r = compute_child_support(case)
    assert r.annual_amount == pytest.approx(0.5 * r.form.amount("305.A"))
    assert r.annual_amount < r.form.amount("602")
    assert any("Capacité de payer" in w for w in r.warnings)


def test_revenus_tires_d_une_declaration():
    """`ParentIncome.from_tax_return` reprend l'emploi, les pensions, placements et gains imposables."""
    tr = compute(Taxpayer(year=2026, age=66, employment_income=40_000, rrif_income=20_000, oas_pension=8_900,
                          eligible_dividends=1_000, interest_income=500, capital_gains=4_000))
    inc = ParentIncome.from_tax_return(tr, union_dues=300)
    assert (inc.salary, inc.pension_benefits, inc.other_income, inc.union_dues) == (40_000, 28_900, 2_000, 300)
    assert inc.investment_income == pytest.approx(1_380 + 500)


def test_json_et_entrees_invalides():
    """`to_dict()` est sérialisable; aucun enfant ou des jours hors de [0, 365] sont refusés."""
    import json
    r = guide((30,), childcare=0)
    assert json.loads(json.dumps(r.to_dict(), ensure_ascii=False))["section"] == "1"
    with pytest.raises(ValueError):
        ChildSupportCase(year=2026, parent_a=PERE, parent_b=MERE, custody_days_a=())
    with pytest.raises(ValueError):
        ChildSupportCase(year=2026, parent_a=PERE, parent_b=MERE, custody_days_a=(400,))
