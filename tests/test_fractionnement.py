# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Fractionnement vérifié sur T1032 et Q : revenus, crédits, retenues et interactions."""

from dataclasses import replace
import json

import pytest

from impotsqc import (Benefits, CoupleOptions, MissingInformationError, PensionIncome,
                      PensionSplit, TaxPayments, Taxpayer, compute, compute_couple, required_couple_questions)
from test_transferts_conjoints import assert_graph
from test_formulaires import test_references_et_parametres_resolvent as check_refs


def person(**values):
    """Contribuable fictif avec couverture, conjoint et versements confirmés."""
    return Taxpayer(**(dict(year=2025, age=66, has_spouse=True,
                           drug_plan_exempt_months=tuple(range(1,13)), payments=TaxPayments(0,0,0,0)) | values))


def choices(**values):
    """Choix de crédits confirmés sans montant fédéral pour conjoint soutenu."""
    return CoupleOptions(**(dict(spouse_amount_claimant="neither", federal_transfers=True) | values))


def split(amount, **values):
    """Choix conjoint avec aucune retenue sur pension et une année complète confirmées."""
    return PensionSplit(**(dict(donor="first", amount=amount, eligible=True, tax_withheld=0,
                                months_as_spouses=12, tax_year_months=12, same_year_survivor_pension=0) | values))


@pytest.mark.parametrize("year", (2025,2026))
def test_choix_distincts_et_transfert_des_retenues(year):
    """Sur 60 000 $, 30 000 $ au fédéral et 20 000 $ au Québec; retenues de 1/2 et 1/3."""
    a=person(year=year, rrif_income=60_000, payments=TaxPayments(10_000,12_000,1000,2000))
    b=person(year=year, age=60, payments=TaxPayments(0,0,500,250))
    pair=compute_couple(a,b,options=choices(federal_pension_split=split(30_000,tax_withheld=10_000),
        quebec_pension_split=split(20_000,tax_withheld=12_000)))
    first, second=pair.first,pair.second
    assert first.federal.amount("23600")==second.federal.amount("23600")==30_000
    assert first.quebec.amount("275")==40_000 and second.quebec.amount("275")==20_000
    assert first.federal.amount("21000")==second.federal.amount("11600")==30_000
    assert first.quebec.amount("245")==second.quebec.amount("123")==20_000
    assert first.federal.amount("31400")==2000 and second.federal.amount("31400")==0
    assert first.federal.amount("43700")==second.federal.amount("43700")==5000
    assert first.quebec.amount("451.1")==second.quebec.amount("451.3")==4000
    assert first.quebec.amount("451.2")==8000 and second.quebec.amount("451.2")==0
    assert {n:line.amount for n,line in first.forms["T1032"].lines.items()} == {
        n:line.amount for n,line in second.forms["T1032"].lines.items()}
    assert first.forms["T1032"]["68020"].refs==("5000-D1:31400-8",)
    assert pair.refs["second/T1032:68020"]==("first/5000-D1:31400-8",)
    assert first.forms["T1032"] is not second.forms["T1032"]
    assert first.forms["T1032"].lines is not second.forms["T1032"].lines
    assert "TP-1.D.Q" not in second.forms
    assert first.forms["TP-1.D.B"].amount("8")==40_000
    assert second.forms["TP-1.D.B"].amount("8")==20_000
    assert first.forms["TP-1.D.B"].amount("8.C")==20_000
    assert first.forms["TP-1.D.F"].amount("46")==20_000
    assert first.forms["TP-1.D.F"].amount("70")==40_000
    assert second.forms["TP-1.D.F"].amount("70")==20_000
    assert pair.refs["second/TP-1:123"]==("first/TP-1.D.Q:22",)
    assert pair.refs["second/TP-1:451.3"]==("first/TP-1.D.Q:58",)
    assert pair.refs["first/TP-1.D.B:1.C"]==("second/TP-1:122","second/TP-1:123")
    assert pair.refs["second/TP-1.D.B:6.C"]==("first/TP-1:245",)
    assert_graph(pair)


def test_rpa_avant_65_ans_et_interdiction_quebec():
    """Une rente RPA est fractionnable au fédéral à 64 ans, mais pas au Québec."""
    a,b=person(age=64,pensions=(PensionIncome(6000,"rpp"),)),person(age=40)
    pair=compute_couple(a,b,options=choices(federal_pension_split=split(3000)))
    assert pair.first.federal.amount("31400")==pair.second.federal.amount("31400")==2000
    assert pair.first.quebec.amount("275")==6000 and pair.second.quebec.amount("275")==0
    assert_graph(pair)
    with pytest.raises(ValueError,match="65 ans"):
        compute_couple(a,b,options=choices(quebec_pension_split=split(3000)))


@pytest.mark.parametrize("income", ({"rrif_income":6000}, {"rrsp_income":6000},
                                     {"oas_pension":6000}, {"qpp_benefits":6000}))
def test_revenus_exclus_avant_65_ans(income):
    """FERR ordinaire avant 65 ans, retraits REER, PSV et RRQ ne deviennent pas fractionnables."""
    with pytest.raises(ValueError,match="maximum admissible"):
        compute_couple(person(age=64,**income),person(),options=choices(federal_pension_split=split(1)))


@pytest.mark.parametrize("kind", ("rrif","rrsp_annuity"))
def test_pension_survivant_avant_65_ans(kind):
    """Un revenu admissible de survivant reste admissible au fédéral avant 65 ans."""
    pair=compute_couple(person(age=60,pensions=(PensionIncome(6000,kind,True),)),person(age=59),
                        options=choices(federal_pension_split=split(3000)))
    assert pair.first.forms["T1032"].amount("68020")==6000
    assert pair.second.federal.amount("31400")==2000
    assert_graph(pair)


@pytest.mark.parametrize("rpa,months,expected", ((0,12,0),(1000,12,500),(3999,12,1999.5),
                                                (4000,12,2000),(3999,6,999.75),(4000,6,2000)))
def test_note1_beneficiaire_avant_65_ans(rpa,months,expected):
    """Note 1 du T1032 : recalcul sous 4 000 $ de pensions admissibles à tout âge."""
    pair=compute_couple(person(rrif_income=10_000,pensions=(PensionIncome(rpa,"rpp"),)),person(age=60),
                        options=choices(federal_pension_split=split(2000,months_as_spouses=months)))
    assert pair.second.forms["T1032"].amount("33")==expected
    assert pair.second.federal.amount("31400")==expected
    assert_graph(pair)


def test_pension_propre_du_beneficiaire():
    """Le T1032 ajoute le droit transféré admissible au revenu propre, puis plafonne à 2 000 $."""
    pair=compute_couple(person(rrif_income=10_000,pensions=(PensionIncome(2000,"rpp"),)),
                        person(age=60,pensions=(PensionIncome(1500,"rpp"),)),
                        options=choices(federal_pension_split=split(3000)))
    assert pair.second.forms["T1032"].amount("32")==1500
    assert pair.second.forms["T1032"].amount("33")==1000
    assert pair.second.forms["T1032"].amount("34")==2500
    assert pair.second.federal.amount("31400")==2000
    assert_graph(pair)


@pytest.mark.parametrize("months,total,maximum", ((12,12,30_000),(6,12,15_000),(3,6,15_000),(1,12,2500)))
def test_prorata_federal_et_limite(months,total,maximum):
    """Nombre de mois d'union et, au décès, durée réduite de l'année fiscale du cédant."""
    a,b=person(rrif_income=60_000),person()
    choice=split(maximum,months_as_spouses=months,tax_year_months=total)
    pair=compute_couple(a,b,options=choices(federal_pension_split=choice))
    assert pair.first.forms["T1032"].amount("21")==maximum
    with pytest.raises(ValueError,match="maximum admissible"):
        compute_couple(a,b,options=choices(federal_pension_split=replace(choice,amount=maximum+0.01)))
    assert_graph(pair)


def test_quebec_sans_prorata_federal():
    """L'annexe Q n'emprunte pas le prorata du T1032; les choix et montants sont distincts."""
    pair=compute_couple(person(rrif_income=60_000),person(),options=choices(
        federal_pension_split=split(7500,months_as_spouses=3),
        quebec_pension_split=PensionSplit("first",30_000,eligible=True,tax_withheld=0)))
    assert pair.first.federal.amount("21000")==7500
    assert pair.first.quebec.amount("245")==30_000
    with pytest.raises(ValueError,match="50 %"):
        compute_couple(person(rrif_income=60_000),person(),options=choices(quebec_pension_split=split(30_001)))
    assert_graph(pair)


def test_recalcul_ae_psv_avant_revenus_quebec():
    """Les remboursements AE puis PSV sont recalculés après 21000, avant TP-1:250."""
    a=person(rrif_income=90_000,oas_pension=9000,benefits=Benefits(ei_regular=5000,ei_repayment_exempt=False))
    b=person()
    old=compute_couple(a,b,options=choices())
    new=compute_couple(a,b,options=choices(federal_pension_split=split(45_000)))
    assert old.first.federal.amount("23500")==pytest.approx(2856.9)
    assert new.first.federal.amount("23400")==59_000
    assert new.first.federal.amount("23500")==new.first.quebec.amount("250")==0
    assert new.first.quebec.amount("275")==104_000
    assert new.second.quebec.amount("275")==0
    assert_graph(new)


def test_fractionnement_reduit_bases_imr():
    """Les déductions de pension sont incluses avant les ajouts des deux régimes d'IMR."""
    a,b=person(rrif_income=30_000,capital_gains=600_000),person()
    old=compute_couple(a,b,options=choices())
    new=compute_couple(a,b,options=choices(federal_pension_split=split(15_000),quebec_pension_split=split(10_000)))
    assert old.first.forms["T691"].amount("P1-93")-new.first.forms["T691"].amount("P1-93")==15_000
    assert old.first.forms["TP-776.42"].amount("22")-new.first.forms["TP-776.42"].amount("22")==10_000
    assert_graph(new)


def test_directions_distinctes_et_symetrie():
    """Chaque régime choisit son cédant; inverser les personnes conserve tous les montants."""
    a,b=person(rrif_income=50_000),person(rrif_income=40_000)
    fed,qc=split(10_000),split(5000,donor="second")
    pair=compute_couple(a,b,options=choices(federal_pension_split=fed,quebec_pension_split=qc))
    reverse=compute_couple(b,a,options=choices(federal_pension_split=replace(fed,donor="second"),
                                             quebec_pension_split=replace(qc,donor="first")))
    assert pair.first.to_dict()==reverse.second.to_dict()
    assert pair.second.to_dict()==reverse.first.to_dict()
    assert "TP-1.D.Q" in pair.second.forms and "TP-1.D.Q" not in pair.first.forms
    assert_graph(pair)


def test_questions_sur_le_choix_et_retenues():
    """Aucun statut, nombre de mois, impôt retenu ou paiement nul n'est deviné."""
    a,b=person(rrif_income=60_000,payments=None),person(payments=None)
    option=choices(federal_pension_split=PensionSplit("first",10_000))
    expected={"first.payments","second.payments"}|{f"options.federal_pension_split.{x}" for x in
        ("eligible","tax_withheld","months_as_spouses","tax_year_months")}
    assert set(required_couple_questions(a,b,options=option))==expected
    with pytest.raises(MissingInformationError) as error:
        compute_couple(a,b,options=option)
    assert set(error.value.questions)==expected
    with pytest.raises(ValueError,match="admissibilité"):
        compute_couple(a,b,options=choices(federal_pension_split=split(10_000,eligible=False)))


@pytest.mark.parametrize("values", ({"donor":"both"},{"amount":-1},{"amount":float('nan')},
    {"tax_withheld":-1},{"eligible":1},{"months_as_spouses":0},{"months_as_spouses":True},
    {"tax_year_months":13},{"months_as_spouses":12,"tax_year_months":6}))
def test_entrees_fractionnement_invalides(values):
    """Les choix incohérents sont refusés avant tout calcul."""
    with pytest.raises(ValueError):
        split(1000,**values) if "amount" not in values else split(**values)


@pytest.mark.parametrize("regime", ("federal","quebec"))
def test_retenue_pension_superieure_au_total(regime):
    """La part admissible ne peut pas excéder les retenues totales confirmées."""
    with pytest.raises(ValueError,match="retenues"):
        compute_couple(person(rrif_income=10_000),person(),
                        options=choices(**{f"{regime}_pension_split":split(1000,tax_withheld=1)}))


def test_choix_zero_ne_construit_ni_document_ni_question():
    """Zéro demandé équivaut à ne pas choisir de fractionnement, même sans retenues saisies."""
    a,b=person(rrif_income=30_000,payments=None),person(payments=None)
    pair=compute_couple(a,b,options=choices(federal_pension_split=PensionSplit("first",0),
                                           quebec_pension_split=PensionSplit("second",0)))
    off=compute_couple(a,b,options=choices())
    assert pair.first.to_dict()==off.first.to_dict()
    assert pair.second.to_dict()==off.second.to_dict()
    assert "T1032" not in pair.first.forms and "TP-1.D.Q" not in pair.second.forms


def test_soldes_reels_distincts_de_la_charge_fiscale():
    """Retenues et acomptes changent le remboursement, sans modifier l'impôt et les cotisations."""
    a=person(has_spouse=False,interest_income=50_000,payments=None)
    before=compute(a)
    assert before.federal_balance is None and before.quebec_balance is None
    assert "federal_balance" not in before.to_dict()["summary"]
    payment=TaxPayments(10_000,20_000,1000,2000)
    result=compute(replace(a,payments=payment))
    assert result.total_payable==before.total_payable
    assert result.federal_balance==pytest.approx(before.federal_payable-11_000)
    assert result.quebec_balance==pytest.approx(before.quebec_payable-22_000)
    assert result.federal.amount("48400")==-result.federal_balance
    assert result.quebec.amount("478")==-result.quebec_balance
    assert result.federal.amount("48500")==result.quebec.amount("479")==0
    payload=json.loads(json.dumps(result.to_dict()))
    assert payload["summary"]["federal_balance"]==round(result.federal_balance,2)
    assert payload["taxpayer"]["payments"]["quebec_instalments"]==2000
    check_refs(result)


@pytest.mark.parametrize("value", (-1,float('nan'),float('inf'),True,"100"))
def test_paiements_invalides(value):
    """Les retenues doivent être des montants finis, non négatifs et explicitement numériques."""
    with pytest.raises(ValueError):
        TaxPayments(value,0,0,0)


@pytest.mark.parametrize("survivor_amount,credit", ((0,0),(2000,1000),(6000,2000)))
def test_note1_annee_de_deces_confirmee(survivor_amount,credit):
    """Le décès dans l'année est distinct de la seule origine de survivant, selon la note 1."""
    a,b=person(pensions=(PensionIncome(6000,"rrif",True),)),person(age=60)
    option=choices(federal_pension_split=split(3000,same_year_survivor_pension=None))
    assert set(required_couple_questions(a,b,options=option))=={"options.federal_pension_split.same_year_survivor_pension"}
    pair=compute_couple(a,b,options=choices(federal_pension_split=split(3000,same_year_survivor_pension=survivor_amount)))
    assert pair.second.federal.amount("31400")==credit
    assert_graph(pair)


def test_origine_survivant_incompatible_et_absence_confirmee():
    """Une origine non survivante explicite suffit à exclure l'exception, sans nouvelle question."""
    a,b=person(pensions=(PensionIncome(6000,"rrif",False),)),person(age=60)
    option=choices(federal_pension_split=split(3000,same_year_survivor_pension=None))
    assert required_couple_questions(a,b,options=option)=={}
    assert compute_couple(a,b,options=option).second.federal.amount("31400")==0
    with pytest.raises(ValueError,match="survivant"):
        compute_couple(a,b,options=choices(federal_pension_split=split(3000,same_year_survivor_pension=1)))


def test_retenue_prorata_utilise_revenu_annuel():
    """T1032:36 divise par 17 (revenu annuel), pas par le revenu réduit de la ligne 19."""
    a,b=person(rrif_income=40_000,payments=TaxPayments(8000,0,0,0)),person()
    pair=compute_couple(a,b,options=choices(federal_pension_split=split(10_000,months_as_spouses=6,tax_withheld=8000)))
    assert pair.first.forms["T1032"].amount("68050")==2000
    assert pair.first.federal.amount("43700")==6000
    assert pair.second.federal.amount("43700")==2000
    assert_graph(pair)



def test_soldes_positifs_avec_retenues_nulles_confirmees():
    """Une absence de paiement confirmée produit le solde dû, sans inventer de remboursement."""
    result=compute(person(has_spouse=False,interest_income=50_000))
    assert result.federal_balance==result.federal_payable>0
    assert result.quebec_balance==result.quebec_payable>0
    assert result.federal.amount("48500")==result.federal_balance
    assert result.quebec.amount("479")==result.quebec_balance
    assert result.federal.amount("48400")==result.quebec.amount("478")==0
    check_refs(result)
