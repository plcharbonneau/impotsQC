# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Chargement et vérification des paramètres annuels (un dossier TOML par année).

Chaque année vit dans `impotsqc/parametres/AAAA/` : `federal.toml`, `quebec.toml`,
`cotisations.toml`, `pension_alimentaire.toml` et `formulaires.toml`. Chaque table y porte une source officielle (`source`), l'endroit où lire la
valeur (`ref`) et un statut (`status`). Les statuts `unpublished` et `incomplete` marquent des
valeurs provisoires ou des règles pas encore calculables; `provisional()` les énumère pour que
les résultats puissent le signaler.
"""

from __future__ import annotations

import tomllib
from importlib.resources import files

FILES = ("federal", "quebec", "cotisations", "pension_alimentaire", "formulaires")
FORM_CODES = frozenset({"T1", "T691", "TP-1", "TP-1.D.B", "TP-1.D.E", "TP-1.D.F", "TP-1.D.K",
                        "TP-752.PC", "TP-776.42", "FIXATION-PA", "5000-S3", "5005-S8", "TP-1.D.G", "TP-1.D.U", "5000-D1"})
STATUSES = frozenset({"published", "rule_2025", "derived", "unpublished", "incomplete"})
PROVISIONAL_STATUSES = frozenset({"unpublished", "incomplete"})
_METADATA = ("source", "ref", "status")


class ParameterError(ValueError):
    """Fichier de paramètres invalide : source manquante, statut inconnu, barème incohérent."""


def _root():
    """Dossier des paramètres, dans le paquet installé."""
    return files("impotsqc") / "parametres"


def available_years() -> list[int]:
    """Années dont les paramètres sont livrés, en ordre croissant."""
    return sorted(int(p.name) for p in _root().iterdir() if p.is_dir() and p.name.isdigit())


def load_parameters(year: int) -> dict[str, dict[str, dict]]:
    """Paramètres fiscaux et catalogue de formulaires de `year`, vérifiés par fichier et table.

    Rend un dictionnaire neuf à chaque appel : le modifier n'altère pas les fichiers.
    """
    folder = _root() / str(year)
    if not folder.is_dir():
        raise ParameterError(f"aucun paramètre pour {year} (années livrées : {available_years()})")
    params = {name: tomllib.loads((folder / f"{name}.toml").read_text(encoding="utf-8")) for name in FILES}
    for name, tables in params.items():
        for key, table in tables.items():
            _check_table(f"{year}/{name}.{key}", table)
    _check_forms(params["formulaires"])
    return params


def _check_forms(forms: dict) -> None:
    """Vérifie la présence des formulaires et les métadonnées propres aux documents."""
    missing = FORM_CODES - forms.keys()
    if missing:
        raise ParameterError(f"formulaires manquants : {sorted(missing)}")
    for code, table in forms.items():
        for key in ("title", "version"):
            if not isinstance(table.get(key), str) or not table[key].strip():
                raise ParameterError(f"formulaires.{code} : {key} doit être une chaîne non vide")
        if not table["source"].lower().endswith(".pdf"):
            raise ParameterError(f"formulaires.{code} : la source doit désigner un PDF officiel")


def provisional(params: dict[str, dict[str, dict]]) -> list[str]:
    """Tables au statut provisoire (`unpublished`, `incomplete`), sous la forme `fichier.table`."""
    return sorted(f"{name}.{key}" for name, tables in params.items()
                  for key, table in tables.items() if table["status"] in PROVISIONAL_STATUSES)


def _check_table(label: str, table: dict) -> None:
    """Vérifie les métadonnées d'une table et, s'il y a lieu, la cohérence de son barème."""
    if not isinstance(table, dict):
        raise ParameterError(f"{label} : une table est attendue")
    missing = [m for m in _METADATA if not table.get(m)]
    if missing:
        raise ParameterError(f"{label} : métadonnées manquantes {missing}")
    if not str(table["source"]).startswith("https://"):
        raise ParameterError(f"{label} : la source doit être une URL https")
    if table["status"] not in STATUSES:
        raise ParameterError(f"{label} : statut inconnu {table['status']!r}")
    if "thresholds" in table:
        thresholds, rates = table["thresholds"], table["rates"]
        if any(b <= a for a, b in zip(thresholds, thresholds[1:])) or len(rates) != len(thresholds) + 1:
            raise ParameterError(f"{label} : seuils non croissants ou nombre de taux incohérent")
    if "upper_bounds" in table:
        bounds = table["upper_bounds"]
        columns = [v for k, v in table.items() if k.startswith("amounts_")]
        if any(b <= a for a, b in zip(bounds, bounds[1:])) or not columns:
            raise ParameterError(f"{label} : bornes non croissantes ou montants absents")
        if any(len(c) != len(bounds) or any(y < x for x, y in zip(c, c[1:])) for c in columns):
            raise ParameterError(f"{label} : colonne de montants de mauvaise longueur ou décroissante")
    for key, value in table.items():
        if key.endswith("rate") and not 0.0 <= value <= 1.0:
            raise ParameterError(f"{label}.{key} : taux hors de [0, 1]")
        if key == "rates" and not all(0.0 <= r <= 1.0 for r in value):
            raise ParameterError(f"{label}.rates : taux hors de [0, 1]")
