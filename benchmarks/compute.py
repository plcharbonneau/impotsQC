# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Mesure reproductible de compute : paramètres chauds, entrées préconstruites, sans JSON.

Exécuter avec PYTHONPATH=src python benchmarks/compute.py. La médiane de sept répétitions de
10 000 appels est exprimée en microsecondes par déclaration. Entrées explicites de la version 0.5.
"""

import json
import platform
import statistics
import timeit

from impotsqc import Taxpayer, compute


def benchmark() -> dict[str, float]:
    """Mesure cinq profils fictifs, sans compter la construction des entrées ni le chargement TOML."""
    household = dict(has_spouse=False, drug_plan_exempt_months=(), drug_plan_dependent_children=0)
    cases = {
        "salarie": Taxpayer(**household, year=2026, age=40, employment_income=80_000),
        "retraite": Taxpayer(**household, year=2026, age=66, rrif_income=30_000, oas_pension=9_000, qpp_benefits=12_000),
        "carriere": Taxpayer(**household, year=2026, age=67, employment_income=45_000),
        "gain_capital": Taxpayer(**household, year=2026, age=50, capital_gains=600_000),
        "sans_revenu": Taxpayer(**household, year=2026, age=40),
    }
    results = {}
    for name, taxpayer in cases.items():
        compute(taxpayer)
        samples = timeit.repeat(lambda: compute(taxpayer), number=10_000, repeat=7)
        results[name] = round(statistics.median(samples) / 10_000 * 1_000_000, 3)
    return results


if __name__ == "__main__":
    print(json.dumps({"python": platform.python_version(), "microseconds": benchmark()}, ensure_ascii=False))
