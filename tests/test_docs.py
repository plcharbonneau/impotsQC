# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Conventions du dépôt : en-tête SPDX et docstring sur chaque module, fonction et classe."""

from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
FICHIERS = sorted((RACINE / "src").rglob("*.py")) + sorted((RACINE / "tests").rglob("*.py"))


def test_en_tete_spdx():
    """Chaque fichier Python commence par l'en-tête de licence."""
    manquants = [f.name for f in FICHIERS if not f.read_text(encoding="utf-8").startswith(
        "# SPDX-License-Identifier: AGPL-3.0-or-later")]
    assert not manquants, manquants


def test_docstrings():
    """Modules, fonctions et classes du code portent une docstring."""
    manquants = []
    for f in sorted((RACINE / "src").rglob("*.py")):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        if not ast.get_docstring(arbre):
            manquants.append(f.name)
        for n in ast.walk(arbre):
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not ast.get_docstring(n):
                manquants.append(f"{f.name}:{n.name}")
    assert not manquants, manquants
