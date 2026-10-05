# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Revenus, récupérations et crédits : cas fictifs chiffrés selon les formulaires officiels."""

import pytest

from impotsqc import (Benefits, Deductions, MissingInformationError, ParentIncome, PensionIncome,
                      Taxpayer, compute, required_questions)
from profiles import single_public_taxpayer


def declaration(**kwargs):
    """Déclaration fictive 2025, sans conjoint, avec assurance privée toute l'année."""
    options = dict(year=2025, age=55, has_spouse=False, drug_plan_exempt_months=tuple(range(1, 13)))
    options.update(kwargs)
    return compute(Taxpayer(**options))


@pytest.mark.parametrize("kind,age,survivor,income_line,credit", [
    ("rpp", 55, None, "11500", 2_000),
    ("rrsp_annuity", 64, False, "12900", 0),
    ("rrsp_annuity", 65, None, "12900", 2_000),
    ("rrsp_annuity", 55, True, "12900", 2_000),
    ("rrif", 64, False, "13000", 0),
    ("rrif", 65, None, "11500", 2_000),
    ("rrif", 55, True, "11500", 2_000),
])
def test_pensions_admissibles(kind, age, survivor, income_line, credit):
    """RPA, rentes REER et FERR suivent leurs règles distinctes d'âge et de survivant."""
    r = declaration(age=age, pensions=(PensionIncome(15_000, kind, survivor),))
    assert r.federal.amount(income_line) == 15_000
    assert r.federal.amount("15000") == r.quebec.amount("199") == 15_000
    assert r.federal.amount("31400") == credit
    assert r.quebec.amount("122") == 15_000
    assert r.quebec.amount("154") == 0
    assert ("5000-D1" in r.forms) == bool(credit)
    assert r.forms["TP-1.D.B"].amount("9") == 3_470


def test_retrait_reer_ordinaire_et_rente_ne_se_confondent_pas():
    """Le retrait REER non échu n'ouvre aucun crédit de pension, même après 65 ans."""
    r = declaration(age=60, rrsp_income=30_000)
    assert r.quebec.amount("122") == 0
    assert r.quebec.amount("154") == r.federal.amount("12900") == 30_000
    assert r.quebec.amount("361") == r.federal.amount("31400") == 0
    assert "TP-1.D.B" not in r.forms
    senior = declaration(age=66, rrsp_income=30_000)
    assert senior.federal.amount("31400") == 0
    assert senior.forms["TP-1.D.B"].amount("9") == 0
    assert ParentIncome.from_tax_return(r).pension_benefits == 30_000
    mixed = declaration(age=66, rrsp_income=30_000,
                        pensions=(PensionIncome(1_000, "rrsp_annuity"),))
    assert mixed.federal.amount("12900") == 31_000
    assert mixed.federal.amount("31400") == 1_000
    assert mixed.quebec.amount("122") == 1_000
    assert mixed.forms["TP-1.D.B"].amount("9") == 1_250


def test_recuperation_ae_avant_psv():
    """Grille 23500 : l'AE de 3 000 $ réduit la base de récupération de la PSV."""
    r = declaration(age=66, interest_income=100_000, oas_pension=9_000,
                    benefits=Benefits(ei_regular=10_000, ei_repayment_exempt=False))
    w = r.forms["5000-D1"]
    assert w.amount("23500-7") == 3_000
    assert w.amount("23500-15") == 116_000
    assert w.amount("23500-19") == pytest.approx(3_381.9)
    assert r.federal.amount("23500") == pytest.approx(6_381.9)
    assert r.federal.amount("23600") == pytest.approx(112_618.1)
    assert r.quebec.amount("250") == r.federal.amount("23500")
    assert r.forms["TP-1.D.F"].amount("44") == 3_000
    assert r.forms["TP-1.D.F"].amount("70") == 107_000


@pytest.mark.parametrize("year,threshold", [(2025, 82_125), (2026, 86_125)])
@pytest.mark.parametrize("excess,repayment", [(0, 0), (100, 30), (20_000, 3_000)])
def test_seuils_recuperation_ae(year, threshold, excess, repayment):
    """Le seuil annuel et le plafond de 30 % des prestations régulières sont indépendants."""
    r = declaration(year=year, interest_income=threshold - 10_000 + excess,
                    benefits=Benefits(ei_regular=10_000, ei_repayment_exempt=False))
    assert r.federal.amount("23500") == repayment


def test_prestations_speciales_rqap_et_exemption_ae():
    """La ligne 11905 détaille 11900 sans doubler le revenu ni provoquer de récupération."""
    b = Benefits(ei_regular=2_000, ei_special=3_000, ei_maternity_parental=4_000,
                 qpip=5_000, ei_repayment_exempt=True)
    r = declaration(interest_income=100_000, benefits=b)
    assert r.federal.amount("11900") == 14_000
    assert r.federal.amount("11905") == 9_000
    assert r.federal.amount("15000") == 114_000
    assert r.quebec.amount("110") == 5_000
    assert r.quebec.amount("111") == 9_000
    assert r.federal.amount("23500") == 0
    assert "5000-D1" not in r.forms
    assert ParentIncome.from_tax_return(r).ei_qpip_benefits == 14_000
    special_only = declaration(interest_income=200_000, benefits=Benefits(ei_special=10_000))
    assert special_only.federal.amount("23500") == 0


def test_srg_non_imposable_et_recuperation_partielle():
    """Le SRG récupéré au-delà de la PSV ne peut plus être déduit une deuxième fois."""
    r = declaration(age=66, interest_income=150_000, oas_pension=8_000,
                    benefits=Benefits(federal_supplements=3_000))
    assert r.federal.amount("15000") == 161_000
    assert r.federal.amount("23500") == pytest.approx(10_131.9)
    assert r.federal.amount("25000") == pytest.approx(868.1)
    assert r.federal.amount("26000") == 150_000
    assert r.quebec.amount("148") == 3_000
    assert r.quebec.amount("295") == pytest.approx(868.1)
    assert r.quebec.amount("299") == 150_000
    assert r.forms["TP-1.D.F"].amount("29") == 3_000
    assert r.forms["TP-1.D.F"].amount("70") == 150_000


def test_trop_percus_et_recuperations_sont_distincts():
    """T4E case 30 réduit le plafond AE; FSS déduit AE/RQAP, mais pas le trop-perçu PSV."""
    b = Benefits(ei_regular=10_000, qpip=5_000, ei_repaid=2_000, qpip_repaid=1_000,
                 oas_overpayment_recovered=1_000, ei_repayment_exempt=False)
    r = declaration(age=66, interest_income=100_000, oas_pension=9_000, benefits=b)
    assert r.federal.amount("23200") == r.quebec.amount("246") == 4_000
    assert r.federal.amount("23400") == 120_000
    w = r.forms["5000-D1"]
    assert w.amount("23500-5") == 8_000
    assert w.amount("23500-7") == 2_400
    assert w.amount("23500-19") == pytest.approx(3_621.9)
    assert r.forms["TP-1.D.F"].amount("41") == 3_000
    assert r.forms["TP-1.D.F"].amount("70") == 109_600


def test_indemnites_exclues_et_redressement_du_montant_personnel():
    """Les indemnités affectent le revenu net, pas le revenu imposable ou la base du FSS."""
    b = Benefits(workers_compensation=30_000, quebec_other_replacement=5_000,
                 quebec_replacement_adjustment=15_000)
    r = declaration(benefits=b)
    assert r.federal.amount("23600") == 30_000
    assert r.federal.amount("25000") == 30_000
    assert r.federal.amount("26000") == 0
    assert r.quebec.amount("275") == 35_000
    assert r.quebec.amount("295") == 35_000
    assert r.quebec.amount("299") == 0
    assert r.quebec.amount("358") == 15_000
    assert r.quebec.amount("359") == r.quebec.amount("377") == 3_571
    assert "TP-1.D.F" not in r.forms


def test_aide_sociale_traitements_et_attribution_distincts():
    """L'aide sociale est déduite au fédéral, reste imposable au Québec et est exclue du FSS."""
    r = declaration(interest_income=20_000,
                    benefits=Benefits(social_assistance=15_000, quebec_social_assistance=7_000))
    assert r.federal.amount("23600") == 35_000
    assert r.federal.amount("25000") == 15_000
    assert r.federal.amount("26000") == 20_000
    assert r.quebec.amount("275") == r.quebec.amount("299") == 27_000
    assert r.forms["TP-1.D.F"].amount("28") == 7_000
    assert r.forms["TP-1.D.F"].amount("70") == 20_000


def test_rpa_et_cotisations_syndicales():
    """RPA déduit des deux revenus; cotisations syndicales déduites au fédéral et créditées à 10 % au Québec."""
    r = declaration(interest_income=50_000,
                    deductions=Deductions(rpp=5_000, union_dues_federal=1_150, union_dues_quebec=1_000))
    assert r.federal.amount("20700") == r.quebec.amount("205") == 5_000
    assert r.federal.amount("21200") == 1_150
    assert r.federal.amount("23600") == 43_850
    assert r.quebec.amount("275") == 45_000
    assert r.quebec.amount("397.1") == 1_000
    assert r.quebec.amount("397") == 100
    assert r.quebec.amount("399") == pytest.approx(2_699.94)
    assert r.forms["TP-1.D.F"].amount("70") == 50_000


def test_imr_revenu_negatif_et_deductions_visees():
    """L'IMR conserve le revenu négatif avant rajouts, puis rajoute la moitié des déductions visées."""
    r = declaration(capital_gains=400_000, rrsp_deduction=450_000)
    assert r.federal.amount("23400") == -250_000
    assert r.federal.amount("23600") == r.federal.amount("26000") == 0
    assert "T691" not in r.forms and "TP-776.42" not in r.forms
    r = declaration(employment_income=30_000, capital_gains=600_000,
                    deductions=Deductions(union_dues_federal=1_000))
    assert r.forms["T691"].amount("P1-51") == 1_000
    assert r.forms["T691"].amount("P1-80") == 632.5  # (265 + 1000) / 2
    q = r.forms["TP-776.42"]
    assert q.amount("157.9") == 1_420
    assert q.amount("157.12") == 0.5
    assert q.amount("158") == 842.5  # (265 + 1420) / 2
    assert q.amount("22") == 629_157.5


@pytest.mark.parametrize("options,missing", [
    ({"pensions": (PensionIncome(15_000, "rrif"),)}, "pensions.0.from_deceased_spouse"),
    ({"benefits": Benefits(ei_regular=10_000)}, "benefits.ei_repayment_exempt"),
    ({"benefits": Benefits(social_assistance=10_000)}, "benefits.quebec_social_assistance"),
    ({"benefits": Benefits(workers_compensation=10_000)}, "benefits.quebec_replacement_adjustment"),
])
def test_informations_requises(options, missing):
    """Une information déterminante inconnue bloque le calcul au lieu d'être présumée."""
    tp = single_public_taxpayer(year=2025, age=55, **options)
    assert missing in required_questions(tp)
    with pytest.raises(MissingInformationError) as error:
        compute(tp)
    assert missing in error.value.to_dict()["questions"]


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1000"])
def test_montants_invalides_refuses(value):
    """Les montants non finis, négatifs ou d'un mauvais type sont refusés avant calcul."""
    for factory in (lambda: Benefits(ei_regular=value), lambda: Deductions(rpp=value),
                    lambda: PensionIncome(value, "rpp"),
                    lambda: single_public_taxpayer(year=2025, age=55, employment_income=value)):
        with pytest.raises(ValueError):
            factory()


def test_prestations_vides_ne_construisent_pas_de_documents():
    """L'absence de montants et d'admissibilité ne crée pas de feuille de travail vide."""
    r = declaration(benefits=Benefits(), deductions=Deductions())
    assert set(r.forms) == {"T1", "TP-1"}


@pytest.mark.parametrize("year,threshold", [(2025, 82_125), (2026, 86_125)])
def test_continuite_ae_et_revenu_disponible_croissant(year, threshold):
    """Les récupérations AE/PSV restent continues et la hausse de revenu reste disponible."""
    b = Benefits(ei_regular=10_000, ei_repayment_exempt=False)
    left = declaration(year=year, interest_income=threshold - 10_000 - 0.01, benefits=b)
    right = declaration(year=year, interest_income=threshold - 10_000 + 0.01, benefits=b)
    assert 0 <= right.total_payable - left.total_payable < 0.02
    previous = declaration(year=year, age=66, interest_income=60_000,
                           oas_pension=9_000, benefits=b).total_payable
    for income in range(61_000, 180_001, 1_000):
        current = declaration(year=year, age=66, interest_income=income,
                              oas_pension=9_000, benefits=b).total_payable
        assert 0 <= current - previous < 1_000
        previous = current


def test_grille_srg_presente_sans_recuperation():
    """Le SRG demande la grille 25000 même lorsque le seuil de récupération n'est pas atteint."""
    r = declaration(age=66, oas_pension=9_000, benefits=Benefits(federal_supplements=5_000))
    assert r.forms["5000-D1"].amount("25000-9") == 14_000
    assert r.federal.amount("25000") == r.quebec.amount("295") == 5_000
    assert r.federal.amount("26000") == 9_000
    assert "23500-21" not in r.forms["5000-D1"].lines


def test_prestations_dans_adaptateur_pension_alimentaire():
    """Les prestations de remplacement sont reprises sans ajouter l'aide sociale exclue."""
    r = declaration(benefits=Benefits(workers_compensation=30_000, quebec_other_replacement=5_000,
                    federal_supplements=3_000, quebec_replacement_adjustment=0,
                    social_assistance=1_000, quebec_social_assistance=1_000))
    parent = ParentIncome.from_tax_return(r)
    assert parent.pension_benefits == 38_000
    assert parent.other_income == 0
