# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Paramètres annuels : schéma, statuts provisoires, et concordance avec un oracle externe.

La concordance croise deux sources indépendantes : les paramètres lus dans les publications
officielles et les relevés d'un oracle externe pour des contribuables fictifs, chaque année. Elle
vérifie chaque règle élémentaire sur les lignes que l'oracle expose (tolérance : arrondi au
dollar). Les relevés vivent dans `oracle/AAAA/cas.json` (ignoré par git) : sans eux, les tests de
concordance sont sautés; ceux du schéma s'exécutent toujours.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impotsqc import rules
from impotsqc.parameters import ParameterError, _check_table, available_years, load_parameters, provisional

RACINE = Path(__file__).resolve().parents[1]
ORACLE = RACINE / "oracle"
ANNEES = [2025, 2026]
PROVISOIRES = {
    2025: [],
    2026: ["quebec.drug_insurance"],
}


@pytest.fixture(params=ANNEES, ids=str)
def annee(request):
    """(année, paramètres, cas de l'oracle ou None) pour chaque année livrée."""
    y = request.param
    fichier = ORACLE / str(y) / "cas.json"
    cas = json.loads(fichier.read_text(encoding="utf-8"))["cas"] if fichier.exists() else None
    return y, load_parameters(y), cas


def _ecarts(cas, fonction, attendu, tol=1.0):
    """Cas où `fonction(entrée, sortie)` s'écarte de la ligne `attendu` de l'oracle de plus de `tol`.

    Saute le test si les relevés de l'oracle sont absents."""
    if cas is None:
        pytest.skip("relevés de l'oracle externe absents (oracle/)")
    out = []
    for c in cas:
        e, s = c["entree"], c["sortie"]
        calcule = fonction(e, s)
        if abs(calcule - abs(s[attendu])) > tol:
            out.append((e["nom"], round(calcule, 2), s[attendu]))
    return out


def test_annees_livrees():
    """Les années livrées sont celles que les tests couvrent."""
    assert available_years() == ANNEES


def test_statuts_provisoires_enumeres(annee):
    """Les valeurs provisoires sont connues et listées, pour être signalées dans les résultats."""
    y, p, _ = annee
    assert provisional(p) == PROVISOIRES[y]


@pytest.mark.parametrize("table", [
    {"x": 1, "ref": "r", "status": "published"},
    {"source": "http://non-securise", "ref": "r", "status": "published"},
    {"source": "https://x", "ref": "r", "status": "devine"},
    {"source": "https://x", "ref": "r", "status": "published", "thresholds": [2, 1], "rates": [0.1, 0.2, 0.3]},
    {"source": "https://x", "ref": "r", "status": "published", "rate": 1.4},
])
def test_tables_invalides_refusees(table):
    """Source absente ou non https, statut inconnu, seuils décroissants, taux > 1 : refus."""
    with pytest.raises(ParameterError):
        _check_table("essai", table)


def test_memes_tables_chaque_annee():
    """Toutes les années ont les mêmes tables et les mêmes clés : une seule implémentation les lit."""
    cles = {y: {f: {t: sorted(v) for t, v in tables.items()} for f, tables in load_parameters(y).items()}
            for y in ANNEES}
    assert cles[2025] == cles[2026]


def test_paliers(annee):
    """Impôt avant crédits = barème de l'année appliqué au revenu imposable, fédéral et Québec."""
    _, p, cas = annee
    assert _ecarts(cas, lambda e, s: rules.bracket_tax(s["revenu_imposable_fed"], p["federal"]["brackets"]),
                   "impot_avant_credits_fed") == []
    assert _ecarts(cas, lambda e, s: rules.bracket_tax(s["revenu_imposable_qc"], p["quebec"]["brackets"]),
                   "impot_avant_credits_qc") == []


def test_montants_federaux(annee):
    """Montant personnel de base (réduit en haut de l'échelle) et montant en raison de l'âge."""
    _, p, cas = annee
    fed = p["federal"]
    assert _ecarts(cas, lambda e, s: rules.federal_basic_personal_amount(s["revenu_net_fed"], fed["basic_personal_amount"]),
                   "montant_base_fed") == []
    assert _ecarts(cas, lambda e, s: rules.federal_age_amount(e["age"], s["revenu_net_fed"], fed["age_amount"]),
                   "montant_age_fed") == []


def test_cotisations_salarie(annee):
    """RRQ (base, supplémentaires), AE et RQAP du salarié, au dixième de dollar; crédit et
    déduction fédéraux de la RRQ."""
    _, p, cas = annee
    cot = p["cotisations"]
    rrq = lambda e: rules.qpp_contributions(e.get("emploi", 0), cot["qpp"])
    assert _ecarts(cas, lambda e, s: rrq(e).total, "rrq_payee", 0.1) == []
    assert _ecarts(cas, lambda e, s: rules.insurable_premium(e.get("emploi", 0), cot["employment_insurance"]),
                   "ae_payee", 0.1) == []
    assert _ecarts(cas, lambda e, s: rules.insurable_premium(e.get("emploi", 0), cot["qpip"]), "rqap_payee", 0.1) == []
    assert _ecarts(cas, lambda e, s: rrq(e).base, "montant_rrq_fed") == []
    assert _ecarts(cas, lambda e, s: rrq(e).enhanced, "deduction_rrq_bonifiee_fed") == []


def test_deduction_travailleurs(annee):
    """6 % du revenu de travail, maximum de l'année."""
    _, p, cas = annee
    t = p["quebec"]["workers_deduction"]
    assert _ecarts(cas, lambda e, s: min(t["maximum"], t["rate"] * e.get("emploi", 0)), "deduction_travailleurs_qc") == []


def test_annexe_b_sans_retraits_reer(annee):
    """Annexe B sans les retraits REER dans les revenus de retraite, comme l'oracle la calcule :
    les montants de l'année concordent. L'écart de règle sur les retraits REER est traité dans
    test_validation_oracle.py."""
    _, p, cas = annee
    f = lambda e, s: rules.schedule_b_amount(age=e["age"], lives_alone=e.get("seul", False),
                                             retirement_income=e.get("revenu_pension", 0),
                                             family_income=s["revenu_net_qc"], table=p["quebec"]["schedule_b"])
    assert _ecarts(cas, f, "montant_age_seul_retraite_qc") == []


def test_credits_dividendes(annee):
    """Crédits fédéral et québécois, en pourcentage du montant majoré."""
    _, p, cas = annee
    for j, table in (("fed", p["federal"]["dividends"]), ("qc", p["quebec"]["dividends"])):
        maj = lambda e: rules.grossed_up_dividends(e.get("div_determines", 0), e.get("div_ordinaires", 0), table)
        assert _ecarts(cas, lambda e, s: rules.dividend_tax_credit(*maj(e), table)[0], f"credit_div_determines_{j}") == []
        assert _ecarts(cas, lambda e, s: rules.dividend_tax_credit(*maj(e), table)[1], f"credit_div_ordinaires_{j}") == []


def test_remboursement_psv_et_abattement(annee):
    """Remboursement de la PSV (15 % au-delà du seuil de l'année) et abattement de 16,5 %."""
    _, p, cas = annee
    fed = p["federal"]

    def psv(e, s):
        avant = s["revenu_net_fed"] - s["remboursement_prestations_fed"]  # la déduction est négative
        return rules.oas_recovery(avant, e.get("psv", 0), fed["oas_recovery"])

    assert _ecarts(cas, psv, "remboursement_psv_ae") == []
    assert _ecarts(cas, lambda e, s: fed["quebec_abatement"]["rate"] * s["impot_net_fed"], "abattement_qc") == []


def test_fss(annee):
    """Base = revenu total moins emploi, PSV et majoration des dividendes."""
    _, p, cas = annee
    qc = p["quebec"]

    def f(e, s):
        reels = e.get("div_determines", 0) + e.get("div_ordinaires", 0)
        majoration = sum(rules.grossed_up_dividends(e.get("div_determines", 0), e.get("div_ordinaires", 0),
                                                    qc["dividends"])) - reels
        base = s["revenu_total_qc"] - e.get("emploi", 0) - e.get("psv", 0) - majoration
        return rules.health_services_fund(base, qc["health_services_fund"])

    assert _ecarts(cas, f, "fss") == []
