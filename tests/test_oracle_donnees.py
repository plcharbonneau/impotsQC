# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Intégrité des relevés de l'oracle externe : provenance consignée, noms uniques, identités
comptables. Les relevés vivent dans `oracle/AAAA/cas.json` (ignoré par git); sans eux, ces tests
sont sautés."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ORACLE = Path(__file__).resolve().parents[1] / "oracle"
FICHIERS = sorted(ORACLE.glob("*/cas.json")) if ORACLE.is_dir() else []
pytestmark = pytest.mark.skipif(not FICHIERS, reason="relevés de l'oracle externe absents (oracle/)")


@pytest.fixture(params=FICHIERS, ids=lambda p: p.parent.name)
def doc(request):
    """Un relevé annuel de l'oracle."""
    return json.loads(request.param.read_text(encoding="utf-8"))


def test_provenance_consignee(doc):
    """L'outil, la date du relevé et l'usage (oracle, jamais source de paramètres) sont consignés."""
    assert doc["source"]["outil"] and doc["source"]["releve_le"]
    assert "oracle" in doc["source"]["usage"].lower()


def test_cas_uniques_et_entrees_documentees(doc):
    """Chaque cas a un nom unique et n'utilise que des entrées décrites dans le glossaire."""
    noms = [c["entree"]["nom"] for c in doc["cas"]]
    assert len(noms) == len(set(noms)) > 0
    glossaire = set(doc["conventions"]["entrees"]) | {"nom"}
    for c in doc["cas"]:
        assert set(c["entree"]) <= glossaire, c["entree"]["nom"]


@pytest.mark.parametrize("j", ["fed", "qc"])
def test_identites_revenu_net(doc, j):
    """Revenu net = revenu total + déductions (négatives), au dollar d'arrondi près."""
    for c in doc["cas"]:
        s = c["sortie"]
        deductions = (s[f"deduction_reer_{j}"] + s[f"deduction_rrq_bonifiee_{j}"]
                      + s[f"remboursement_prestations_{j}"] + (s["deduction_travailleurs_qc"] if j == "qc" else 0))
        assert abs(s[f"revenu_total_{j}"] + deductions - s[f"revenu_net_{j}"]) <= 2, c["entree"]["nom"]
