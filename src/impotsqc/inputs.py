# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Entrées fiscales par situation, indépendantes des numéros et classes de formulaires."""

from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite


def validate_amounts(instance) -> None:
    """Refuse les montants non numériques, non finis ou négatifs, y compris les booléens."""
    for field in fields(instance):
        if field.type not in ("float", "float | None"):
            continue
        value = getattr(instance, field.name)
        if value is None and field.type == "float | None":
            continue
        if type(value) not in (int, float) or not isfinite(value) or value < 0:
            raise ValueError(f"{field.name} doit être un montant fini et non négatif")


@dataclass(frozen=True)
class PensionIncome:
    """Pension canadienne : rente de RPA, rente de REER échu ou paiement de FERR/FRV.

    `kind` vaut `rpp`, `rrsp_annuity` ou `rrif`. Les paiements forfaitaires de RPA ne sont
    pas des rentes de RPA. `from_deceased_spouse` confirme si le revenu découle du décès
    du conjoint; il est demandé avant 65 ans pour un FERR ou une rente REER.
    Ne pas répéter ici un montant déjà fourni dans `Taxpayer.rrif_income`.
    """

    amount: float
    kind: str
    from_deceased_spouse: bool | None = None

    def __post_init__(self) -> None:
        """Valide le type de pension, son montant et l'origine de survivant lorsqu'elle est connue."""
        validate_amounts(self)
        if self.kind not in {"rpp", "rrsp_annuity", "rrif"}:
            raise ValueError("kind doit être rpp, rrsp_annuity ou rrif")
        if self.from_deceased_spouse is not None and type(self.from_deceased_spouse) is not bool:
            raise ValueError("from_deceased_spouse doit être True, False ou None")


@dataclass(frozen=True)
class Benefits:
    """Prestations reçues, en dollars canadiens, séparées selon leur traitement fiscal.

    `ei_special` exclut les prestations de maternité/parentales, fournies séparément dans
    `ei_maternity_parental`; toutes les entrées AE excluent le RQAP (`qpip`). L'exemption du
    remboursement d'AE doit être confirmée (historique des prestations / case 7 du T4E).
    `workers_compensation` correspond aux indemnités d'accident du travail déclarables au
    fédéral; `quebec_other_replacement` contient les autres indemnités déclarables seulement
    au Québec, dont celles de la SAAQ. Le redressement québécois doit être fourni à partir
    de la case M du relevé 5, y compris zéro : il ne se déduit pas du montant reçu.
    `social_assistance` est le montant attribué au fédéral selon les règles du ménage;
    `quebec_social_assistance` est celui du relevé 5, qui peut être différent.
    Les remboursements `ei_repaid`, `qpip_repaid` et `oas_overpayment_recovered` concernent
    les trop-perçus déductibles cette année, pas les récupérations calculées selon le revenu.
    Aucun choix de report du remboursement à une année passée n'est effectué.
    """

    ei_regular: float = 0.0
    ei_special: float = 0.0
    ei_maternity_parental: float = 0.0
    qpip: float = 0.0
    federal_supplements: float = 0.0
    workers_compensation: float = 0.0
    social_assistance: float = 0.0
    quebec_social_assistance: float | None = None
    ei_repaid: float = 0.0
    qpip_repaid: float = 0.0
    oas_overpayment_recovered: float = 0.0
    quebec_other_replacement: float = 0.0
    quebec_replacement_adjustment: float | None = None
    ei_repayment_exempt: bool | None = None

    def __post_init__(self) -> None:
        """Vérifie les montants et la réponse explicite sur l'exemption d'AE."""
        validate_amounts(self)
        if self.ei_repayment_exempt is not None and type(self.ei_repayment_exempt) is not bool:
            raise ValueError("ei_repayment_exempt doit être True, False ou None")
        if (self.quebec_replacement_adjustment
                and not (self.workers_compensation or self.quebec_other_replacement)):
            raise ValueError("un redressement requiert des indemnités de remplacement du revenu")


@dataclass(frozen=True)
class Deductions:
    """Cotisations admissibles déclarées, après exclusion des montants non admissibles.

    `rpp` : déduction de cotisations RPA (T1 20700 et TP-1 205).
    Les cotisations syndicales/professionnelles ont deux bases distinctes : au fédéral elles
    sont déductibles; au Québec elles ouvrent un crédit et excluent notamment les taxes dont
    le remboursement peut être demandé. Les montants ne sont donc jamais copiés implicitement.
    """

    rpp: float = 0.0
    union_dues_federal: float = 0.0
    union_dues_quebec: float = 0.0

    def __post_init__(self) -> None:
        """Vérifie que les cotisations sont des montants finis et non négatifs."""
        validate_amounts(self)


@dataclass(frozen=True)
class CoupleOptions:
    """Admissibilité et choix de crédits entre les deux déclarants d’un couple.

    `spouse_amount_claimant` vaut first, second ou neither; il confirme la personne qui
    subvient aux besoins de son conjoint et demande le montant fédéral correspondant.
    `spouse_caregiver` confirme l’admissibilité de ce demandeur au supplément pour infirmité.
    `federal_transfers` confirme les conditions de transfert de l’annexe 2, notamment l’absence
    de séparation pour rupture de 90 jours incluant le 31 décembre. None signifie inconnu.
    """

    spouse_amount_claimant: str | None = None
    spouse_caregiver: bool | None = None
    federal_transfers: bool | None = None
    transfer_unused_quebec: bool = True

    def __post_init__(self) -> None:
        """Valide les réponses sans assimiler une absence de réponse à une inadmissibilité."""
        if self.spouse_amount_claimant not in (None, "first", "second", "neither"):
            raise ValueError("spouse_amount_claimant doit être first, second, neither ou None")
        for name in ("spouse_caregiver", "federal_transfers"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise ValueError(f"{name} doit être True, False ou None")
        if type(self.transfer_unused_quebec) is not bool:
            raise ValueError("transfer_unused_quebec doit être True ou False")
        if self.spouse_amount_claimant == "neither" and self.spouse_caregiver:
            raise ValueError("un demandeur doit être choisi pour le montant canadien pour aidant du conjoint")
