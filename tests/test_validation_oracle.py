# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Validation ligne par ligne contre un oracle externe, contribuables fictifs, par année.

Les relevés de l'oracle vivent hors du dépôt, dans `oracle/AAAA/cas.json` (ignoré par git) : sans
eux, ces tests sont sautés. Chaque relevé déclare ses écarts connus (`ecarts_connus`), que le test
vérifie à leur valeur exacte :

- `ramq_maximum` : maximum de la cotisation au régime d'assurance médicaments retenu par l'oracle
  quand il diffère du maximum officiel de l'année;
- `annexe_b_sans_retraits_reer` : l'oracle exclut les retraits REER des revenus de retraite de
  l'annexe B, que le formulaire officiel inclut (ligne 122);
- `imr_quebec_non_calcule` : l'oracle n'estime l'impôt minimum qu'au fédéral; quand l'impôt minimum
  du Québec s'applique, il rapporte l'impôt ordinaire du Québec.

Toute autre différence au-delà de l'arrondi (1 $ par ligne, 2 $ sur les totaux) fait échouer le test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impotsqc import Taxpayer, compute, load_parameters, rules

ORACLE = Path(__file__).resolve().parents[1] / "oracle"
ANNEES = sorted(int(p.parent.name) for p in ORACLE.glob("*/cas.json")) if ORACLE.is_dir() else []
pytestmark = pytest.mark.skipif(not ANNEES, reason="relevés de l'oracle externe absents (oracle/)")
DOCS = {y: json.loads((ORACLE / str(y) / "cas.json").read_text(encoding="utf-8")) for y in ANNEES}
QC = {y: load_parameters(y)["quebec"] for y in ANNEES}

ENTREES = {"emploi": "employment_income", "psv": "oas_pension", "rrq": "qpp_benefits", "retrait_reer": "rrsp_income",
           "revenu_pension": "rrif_income", "gain_capital": "capital_gains", "div_determines": "eligible_dividends",
           "div_ordinaires": "other_dividends", "autre_revenu": "interest_income", "deduction_reer": "rrsp_deduction",
           "seul": "lives_alone"}

LIGNES = {  # champ du relevé -> (formulaire, ligne)
    "revenu_total_fed": ("T1", "15000"), "revenu_total_qc": ("TP-1", "199"),
    "deduction_reer_fed": ("T1", "20800"), "deduction_reer_qc": ("TP-1", "214"),
    "deduction_rrq_bonifiee_fed": ("T1", "22215"), "deduction_rrq_bonifiee_qc": ("TP-1", "248"),
    "deduction_travailleurs_qc": ("TP-1", "201"),
    "remboursement_prestations_fed": ("T1", "23500"), "remboursement_prestations_qc": ("TP-1", "250"),
    "revenu_net_fed": ("T1", "23600"), "revenu_net_qc": ("TP-1", "275"),
    "revenu_imposable_fed": ("T1", "26000"), "revenu_imposable_qc": ("TP-1", "299"),
    "impot_avant_credits_fed": ("T1", "40400"), "impot_avant_credits_qc": ("TP-1", "401"),
    "montant_base_fed": ("T1", "30000"), "montant_base_qc": ("TP-1", "350"),
    "montant_age_fed": ("T1", "30100"), "montant_age_seul_retraite_qc": ("TP-1", "361"),
    "montant_emploi_fed": ("T1", "31260"), "montant_pension_fed": ("T1", "31400"),
    "montant_ae_fed": ("T1", "31200"), "montant_rrq_fed": ("T1", "30800"), "montant_rqap_fed": ("T1", "31205"),
    "total_montants_fed": ("T1", "33500"), "credits_non_remb_fed": ("T1", "35000"),
    "credit_prolongation_carriere_qc": ("TP-1", "391"),
    "impot_base_fed": ("T1", "42900"), "impot_net_fed": ("T1", "42000"), "impot_qc": ("TP-1", "432"),
    "abattement_qc": ("T1", "44000"), "remboursement_psv_ae": ("T1", "42200"),
    "fss": ("TP-1", "446"), "prime_ramq": ("TP-1", "447"),
    "ae_payee": ("T1", "31200"), "rqap_payee": ("TP-1", "97"),
    "ligne_41700_fed": ("T1", "41700"),
}


def contribuable(year: int, entree: dict) -> Taxpayer:
    """Contribuable impotsqc équivalent à une entrée du relevé."""
    return Taxpayer(year=year, age=entree["age"], **{ENTREES[k]: v for k, v in entree.items() if k in ENTREES})


def valeurs(r) -> dict[str, float]:
    """Montants impotsqc sous les noms des champs du relevé."""
    out = {k: (r.federal if f == "T1" else r.quebec).amount(n) for k, (f, n) in LIGNES.items()}
    out["rrq_payee"] = r.quebec.amount("98") + r.quebec.amount("98.2")
    out["div_fed"], out["div_qc"] = r.federal.amount("40425"), r.quebec.amount("415")
    out["total_fed"], out["total_qc"], out["total_impots_cotisations"] = r.federal_payable, r.quebec_payable, r.total_payable
    out["imr_supplement_fed"] = r.federal.amount("41700") - r.federal.amount("40600")
    return out


def ecarts_attendus(year: int, entree: dict, sortie: dict, r) -> dict[str, float]:
    """Écarts déclarés (impotsqc − oracle) pour ce cas, recalculés à partir de leur cause."""
    qc, connus = QC[year], DOCS[year].get("ecarts_connus", {})
    ramq = 0.0
    if connus.get("ramq_maximum") is not None and sortie["prime_ramq"] == connus["ramq_maximum"]:
        assert r.quebec.amount("447") == qc["drug_insurance"]["annual_maximum"]
        ramq = r.quebec.amount("447") - sortie["prime_ramq"]
    attendus: dict[str, float] = {}
    impot_qc = 0.0
    if connus.get("annexe_b_sans_retraits_reer") and entree.get("retrait_reer"):
        sans_reer = rules.schedule_b_amount(age=entree["age"], lives_alone=entree.get("seul", False),
                                            retirement_income=entree.get("revenu_pension", 0),
                                            family_income=r.quebec.amount("275"), table=qc["schedule_b"])
        assert abs(sans_reer - sortie["montant_age_seul_retraite_qc"]) <= 1  # l'oracle = règle sans REER
        delta_361 = r.quebec.amount("361") - sans_reer
        attendus["montant_age_seul_retraite_qc"] = delta_361
        impot_qc = -qc["credits"]["rate"] * delta_361
        attendus["impot_qc"] = impot_qc
    if connus.get("imr_quebec_non_calcule"):
        impot_qc += r.quebec.amount("432") - max(0.0, r.quebec.amount("430"))
        attendus["impot_qc"] = impot_qc
    attendus["prime_ramq"] = ramq
    attendus["total_qc"] = attendus["total_impots_cotisations"] = ramq + impot_qc
    return attendus


CAS = [(y, c) for y in ANNEES for c in DOCS[y]["cas"]]


@pytest.mark.parametrize(("year", "cas"), CAS, ids=[f"{y}-{c['entree']['nom']}" for y, c in CAS])
def test_ligne_par_ligne(year, cas):
    """Chaque ligne concorde avec l'oracle, à l'écart déclaré près."""
    entree, sortie = cas["entree"], dict(cas["sortie"])
    sortie["div_fed"] = abs(sortie["credit_div_determines_fed"]) + abs(sortie["credit_div_ordinaires_fed"])
    sortie["div_qc"] = abs(sortie["credit_div_determines_qc"]) + abs(sortie["credit_div_ordinaires_qc"])
    r = compute(contribuable(year, entree))
    attendus = ecarts_attendus(year, entree, sortie, r)
    problemes = []
    for champ, calcule in valeurs(r).items():
        if champ not in sortie:  # champ absent des relevés les plus anciens
            continue
        tol = 2.0 if champ.startswith("total") else 1.0
        ecart = calcule - abs(sortie[champ]) - attendus.get(champ, 0.0)
        if abs(ecart) > tol:
            problemes.append(f"{champ}: impotsqc {calcule:.2f}, oracle {sortie[champ]}, écart inexpliqué {ecart:+.2f}")
    assert not problemes, "\n".join(problemes)


@pytest.mark.parametrize("year", ANNEES)
def test_ecarts_declares_existent_vraiment(year):
    """Les écarts déclarés ne sont pas nuls : si l'oracle se corrige, le test le dira."""
    connus = DOCS[year].get("ecarts_connus", {})
    reer = [c for c in DOCS[year]["cas"] if c["entree"].get("retrait_reer")]
    deltas = [ecarts_attendus(year, c["entree"], c["sortie"], compute(contribuable(year, c["entree"])))
              .get("montant_age_seul_retraite_qc", 0.0) for c in reer]
    assert sum(1 for d in deltas if d > 1) == connus.get("nombre_cas_reer", 0)
    ramq = connus.get("ramq_maximum")
    assert sum(1 for c in DOCS[year]["cas"] if ramq is not None and c["sortie"]["prime_ramq"] == ramq) \
        == connus.get("nombre_cas_ramq", 0)
