# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Contribuables fictifs aux hypothèses explicites pour les tests historiques."""

from impotsqc import Taxpayer


def single_public_taxpayer(**kwargs) -> Taxpayer:
    """Profil sans conjoint ni enfant, assujetti à la RAMQ douze mois, comme avant 0.5."""
    return Taxpayer(has_spouse=False, drug_plan_exempt_months=(), drug_plan_dependent_children=0, **kwargs)
