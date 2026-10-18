# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Retenues, acomptes et soldes des déclarations, distincts de la charge fiscale annuelle."""

from __future__ import annotations

from .model import Form, Taxpayer


def settle_tax_payments(tp: Taxpayer, forms: dict[str, Form], *, federal_recipient: bool = False,
                        quebec_received: float | None = None) -> None:
    """Remplit les soldes seulement si les retenues et acomptes réels ont été confirmés.

    Les crédits remboursables déjà calculés sont repris; aucun crédit absent n'est présumé.
    Les soldes sont arithmétiques, avant intérêts, pénalités et tolérances de perception.
    Les transferts de remboursement entre conjoints ne sont pas des transferts de pension.
    """
    payment = tp.payments
    if payment is None:
        return
    federal, quebec = forms["T1"], forms["TP-1"]
    if "T1032" in forms:
        number = "42" if federal_recipient else "39"
        federal.add("43700", "Impôt total retenu", forms["T1032"].amount(number), refs=(f"T1032:{number}",))
    else:
        federal.add("43700", "Impôt total retenu", payment.federal_withheld, "retenues fédérales des feuillets, hors impôt québécois")
    federal.add("43850", "Impôt retenu après transfert au Québec", federal.amount("43700"),
                "aucun transfert d'impôt retenu dans une autre province saisi", refs=("T1:43700",))
    federal.add("47600", "Impôt payé par acomptes provisionnels", payment.federal_instalments)
    codes = tuple(n for n in ("43850", "44000", "45100", "45200", "45300", "45350", "45355", "45400",
                             "45600", "45700", "46900", "47555", "47556", "47600") if n in federal.lines)
    paid = federal.add("48200", "Total des crédits", sum(federal.amount(n) for n in codes),
                        refs=tuple(f"T1:{n}" for n in codes))
    balance = federal.add("172", "Remboursement ou solde dû", federal.amount("43500") - paid,
                           refs=("T1:43500", "T1:48200"))
    federal.add("48400", "Remboursement", max(0.0, -balance), "valeur absolue du solde négatif", refs=("T1:172",))
    federal.add("48500", "Solde dû", max(0.0, balance), refs=("T1:172",))

    withheld = quebec.add("451", "Impôt du Québec retenu à la source", payment.quebec_withheld,
                          "retenues initiales des relevés, avant tout transfert de pension")
    refs = ("TP-1:451",)
    if "TP-1.D.Q" in forms:
        withheld -= quebec.add("451.1", "Impôt du Québec retenu transféré au conjoint", forms["TP-1.D.Q"].amount("58"),
                               refs=("TP-1.D.Q:58",))
        refs += ("TP-1:451.1",)
    quebec.add("451.2", "Montant de la ligne 451 moins celui de la ligne 451.1", withheld, refs=refs)
    if quebec_received is not None:
        quebec.add("451.3", "Impôt du Québec retenu transféré par le conjoint", quebec_received,
                   "ligne 58 de l'annexe Q du conjoint; lien dans CoupleReturn.refs")
    quebec.add("453", "Impôt payé par acomptes provisionnels", payment.quebec_instalments)
    codes = tuple(n for n in ("451.2", "451.3", "452", "453", "454", "455", "456", "457", "458",
                             "459", "460", "462", "463") if n in quebec.lines)
    paid = quebec.add("465", "Impôt payé et autres crédits", sum(quebec.amount(n) for n in codes),
                      refs=tuple(f"TP-1:{n}" for n in codes))
    quebec.add("468", "Total de l'impôt payé et des autres crédits", paid, "aucune compensation pour maintien à domicile saisie",
               refs=("TP-1:465",))
    balance = quebec.add("470", "Remboursement ou solde à payer", quebec.amount("450") - paid,
                         refs=("TP-1:450", "TP-1:468"))
    refund = quebec.add("474", "Montant à rembourser", max(0.0, -balance), "valeur absolue du solde négatif", refs=("TP-1:470",))
    due = quebec.add("475", "Solde à payer avant transfert du remboursement du conjoint", max(0.0, balance), refs=("TP-1:470",))
    quebec.add("478", "Remboursement", refund, "aucun transfert de remboursement demandé", refs=("TP-1:474",))
    quebec.add("479", "Solde à payer", due, "aucun remboursement reçu du conjoint; avant tolérance de perception", refs=("TP-1:475",))
