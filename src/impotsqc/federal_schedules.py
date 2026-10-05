# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Annexes fédérales : parties couvertes, avec la numérotation des documents officiels."""

from __future__ import annotations

from . import rules
from .model import Form, Line, Taxpayer


def minimum_tax(tp: Taxpayer, params: dict, federal: Form, dividend_gross_up: float) -> Form | None:
    """Remplit le T691 si le revenu rajusté dépasse l'exemption, avec une base signée avant rajouts."""
    t = params["federal"]["minimum_tax"]
    inclusion = params["federal"]["capital_gains"]["inclusion_rate"]
    taxable = federal.amount("23400") - federal.amount("23500") - federal.amount("25000")
    enhanced, dues = federal.amount("22215"), federal.amount("21200")
    amt = rules.minimum_tax(taxable_income=taxable, capital_gains=tp.capital_gains, capital_gains_inclusion=inclusion,
                            addback_deductions=enhanced + dues, dividend_gross_up=dividend_gross_up,
                            credits=federal.amount("33800"), table=t)
    if amt.net_adjusted_taxable_income <= 0:
        return None
    f = Form.from_parameters("T691", params)
    f.add("P1-1", "Revenu imposable", taxable, "recalcul sans plancher à zéro au revenu net ou imposable",
          refs=("T1:23400", "T1:23500") + (("T1:25000",) if "25000" in federal.lines else ()))
    gains = f.add("P1-23", "Partie non imposable des gains en capital", tp.capital_gains * (t["capital_gains_inclusion"] - inclusion),
                  "gain réalisé × différence des taux d'inclusion",
                  refs=("T1:12700",),
                  params=("federal.capital_gains.inclusion_rate", "federal.minimum_tax.capital_gains_inclusion"))
    f.add("P1-58", "Déduction pour les cotisations bonifiées au RPC ou au RRQ", enhanced,
          refs=("T1:22215",))
    deduction_refs = ("T691:P1-58",)
    if "21200" in federal.lines:
        f.add("P1-51", "Cotisations annuelles syndicales, professionnelles et semblables", dues,
              refs=("T1:21200",))
        deduction_refs += ("T691:P1-51",)
    addback = f.add("P1-80", "Déductions rajoutées", t["deduction_addback_rate"] * (enhanced + dues),
                    "déductions visées dans la portée", refs=deduction_refs,
                    params=("federal.minimum_tax.deduction_addback_rate",))
    f.add("P1-83", "Revenu avant réductions", taxable + gains + addback, "lignes 1 + 23 + 80 dans la portée",
          refs=("T691:P1-1", "T691:P1-23", "T691:P1-80"))
    f.add("P1-86", "Majoration des dividendes", dividend_gross_up, "montant imposable moins dividendes réels",
          refs=("T1:12000", "T1:12010"),
          params=("federal.dividends.eligible_gross_up", "federal.dividends.other_gross_up"))
    f.add("P1-93", "Revenu imposable rajusté", amt.adjusted_taxable_income, "ligne 83 − ligne 86 dans la portée",
          refs=("T691:P1-83", "T691:P1-86"))
    f.add("P1-94", "Exemption de base", t["exemption"],
          params=("federal.minimum_tax.exemption",))
    f.add("P1-95", "Revenu imposable net rajusté", amt.net_adjusted_taxable_income, "ligne 93 − ligne 94, minimum zéro",
          refs=("T691:P1-93", "T691:P1-94"))
    f.add("P1-96", "Taux d'impôt fédéral", t["rate"], "taux exprimé comme fraction",
          params=("federal.minimum_tax.rate",))
    f.add("P1-97", "Montant minimum brut", t["rate"] * amt.net_adjusted_taxable_income,
          refs=("T691:P1-95", "T691:P1-96"))
    credits = f.add("P1-98", "Crédits d'impôt non remboursables nets", t["credit_fraction"] * federal.amount("33800"),
                    refs=("T1:33800",),
                    params=("federal.minimum_tax.credit_fraction",))
    f.add("P1-102", "Total des crédits admis", credits, "aucun autre crédit visé dans la portée",
          refs=("T691:P1-98",))
    f.add("P1-103", "Montant minimum", amt.minimum_amount, "ligne 97 − ligne 102, minimum zéro",
          refs=("T691:P1-97", "T691:P1-102"))
    f.add("P5-1", "Montant minimum", amt.minimum_amount,
          refs=("T691:P1-103",))
    ordinary = f.add("P5-4", "Impôt fédéral ordinaire net à payer", federal.amount("40600"),
                     "aucun crédit étranger, surtaxe ni crédit d'investissement dans la portée",
                     refs=("T1:40600",))
    extra = f.add("P5-11", "Impôt minimum additionnel", max(0.0, amt.minimum_amount - ordinary),
                  "lignes 1 − 4 dans la portée, minimum zéro",
                  refs=("T691:P5-1", "T691:P5-4"))
    if extra > 0:
        f.add("P6-3", "Impôt fédéral de base hors revenu fractionné", federal.amount("42900"),
              refs=("T1:42900",))
        f.add("P6-4", "Montant minimum", amt.minimum_amount,
              refs=("T691:P1-103",))
        f.add("P6-7", "Impôt fédéral de base aux fins de l'abattement", max(federal.amount("42900"), amt.minimum_amount),
              "aucun impôt sur le revenu fractionné",
              refs=("T691:P6-3", "T691:P6-4"))
        f.add("P6-14", "Impôt fédéral à payer dans le cadre de l'IMR", amt.minimum_amount,
              "aucune surtaxe ni impôt sur le revenu fractionné",
              refs=("T691:P6-4",))
    return f


def capital_gains(tp: Taxpayer, params: dict) -> Form | None:
    """Annexe 3, total net fourni et inclusion; aucune ventilation des transactions n'est inventée."""
    if tp.capital_gains <= 0:
        return None
    f = Form.from_parameters("5000-S3", params)
    f.add("19700", "Total des gains ou pertes en capital", tp.capital_gains,
          "ligne 21 : gain net fourni, avant inclusion; détail des dispositions non fourni")
    f.add("22", "Montant de la ligne 21", tp.capital_gains, refs=("5000-S3:19700",))
    rate = f.add("23", "Taux d'inclusion", params["federal"]["capital_gains"]["inclusion_rate"],
                 "taux exprimé comme fraction", params=("federal.capital_gains.inclusion_rate",))
    taxable = f.add("24", "Montant de la ligne 22 multiplié par le pourcentage de la ligne 23",
                    tp.capital_gains * rate, refs=("5000-S3:22", "5000-S3:23"))
    f.add("19900", "Total des gains en capital imposables ou des pertes en capital nettes", taxable,
          "ligne 26 : aucun gain à inclusion de 100 % dans les entrées du moteur", refs=("5000-S3:24",))
    return f


def qpp_employment(tp: Taxpayer, params: dict, qpp: rules.QppContributions) -> Form | None:
    """Annexe 8, emploi québécois toute l'année, retenues simulées égales aux cotisations requises.

    Les choix de cessation, trop-perçus et proratas mensuels ne sont pas modélisés. À 18 ans
    et dès 73 ans, les calculs historiques restent au T1 sans produire une annexe trompeuse.
    """
    if tp.employment_income <= 0 or not 19 <= tp.age <= 72:
        return None
    t = params["cotisations"]["qpp"]
    f = Form.from_parameters("5005-S8", params)
    maximum = float(t["maximum_pensionable_earnings"])
    additional = float(t["additional_maximum_pensionable_earnings"])
    exemption = float(t["basic_exemption"])
    pensionable = float(min(tp.employment_income, additional))
    above = max(0.0, pensionable - maximum)
    capped = float(min(tp.employment_income, maximum))
    # Construction groupée des lignes immuables : même modèle, moins d’appels par déclaration.
    f.lines = {line.number: line for line in (
        Line("P1-A", "Nombre de mois pendant lesquels le RRQ s'est appliqué", 12.0,
             "hypothèse d'emploi québécois assujetti toute l'année, sans choix de cessation"),
        Line("P1-B", "Maximum des gains ouvrant droit à pension", maximum,
             refs=("5005-S8:P1-A",),
             params=("cotisations.qpp.maximum_pensionable_earnings",)),
        Line("P1-D", "Maximum supplémentaire des gains ouvrant droit à pension", additional,
             refs=("5005-S8:P1-A",),
             params=("cotisations.qpp.additional_maximum_pensionable_earnings",)),
        Line("P1-E", "Exemption de base maximale", exemption,
             refs=("5005-S8:P1-A",),
             params=("cotisations.qpp.basic_exemption",)),
        Line("P2-1", "Total des gains ouvrant droit à pension du RRQ", pensionable,
             "case 26 simulée d'un feuillet T4, plafonnée au maximum supplémentaire",
             refs=("T1:10100", "5005-S8:P1-D")),
        Line("P2-2", "Moins élevé des montants de la ligne D et de la ligne 1", pensionable,
             refs=("5005-S8:P1-D", "5005-S8:P2-1")),
        Line("P2-3", "Montant de la ligne B", maximum,
             refs=("5005-S8:P1-B",)),
        Line("P2-4", "Gains soumis aux deuxièmes cotisations supplémentaires", above,
             refs=("5005-S8:P2-2", "5005-S8:P2-3")),
        Line("P2-5", "Montant de la ligne 2 moins celui de la ligne 4", capped,
             refs=("5005-S8:P2-2", "5005-S8:P2-4")),
        Line("P2-6", "Montant de la ligne E", exemption,
             refs=("5005-S8:P1-E",)),
        Line("P2-7", "Gains soumis aux cotisations de base et premières cotisations supplémentaires", max(0.0, capped - exemption),
             refs=("5005-S8:P2-5", "5005-S8:P2-6")),
        Line("P2-8", "Total des cotisations de base et premières cotisations supplémentaires réelles", qpp.base + qpp.first_additional,
             "case 17 simulée : retenues égales aux cotisations requises",
             refs=("5005-S8:P2-11", "5005-S8:P2-12")),
        Line("P2-9", "Cotisations de base réelles", qpp.base,
             "part de base calculée sans arrondi intermédiaire",
             refs=("5005-S8:P2-8",),
             params=("cotisations.qpp.base_rate", "cotisations.qpp.first_additional_rate")),
        Line("P2-10", "Premières cotisations supplémentaires réelles", qpp.first_additional,
             "part supplémentaire calculée sans soustraction de montants arrondis",
             refs=("5005-S8:P2-8", "5005-S8:P2-9")),
        Line("P2-11", "Cotisations de base requises", qpp.base,
             refs=("5005-S8:P2-7",),
             params=("cotisations.qpp.base_rate",)),
        Line("P2-12", "Premières cotisations supplémentaires requises", qpp.first_additional,
             refs=("5005-S8:P2-7",),
             params=("cotisations.qpp.first_additional_rate",)),
        Line("P2-13", "Cotisations de base et premières cotisations supplémentaires requises", qpp.base + qpp.first_additional,
             refs=("5005-S8:P2-11", "5005-S8:P2-12")),
        Line("P2-21", "Total des deuxièmes cotisations supplémentaires réelles", qpp.second_additional,
             "case 17A simulée : retenue égale à la cotisation requise",
             refs=("5005-S8:P2-22",)),
        Line("P2-22", "Deuxièmes cotisations supplémentaires requises", qpp.second_additional,
             refs=("5005-S8:P2-4",),
             params=("cotisations.qpp.second_additional_rate",)),
        Line("P2-24", "Montant de la ligne 20 plus celui de la ligne 23", 0.0,
             "retenues simulées égales aux cotisations requises; différences nulles aux lignes 16 à 23",
             refs=("5005-S8:P2-8", "5005-S8:P2-13", "5005-S8:P2-21", "5005-S8:P2-22")),
        Line("P2-35", "Cotisations de base au RRQ pour les revenus d'emploi", qpp.base,
             "partie 2b : aucun excédent ni manque à répartir; montant de la ligne 11",
             refs=("5005-S8:P2-11", "5005-S8:P2-24")),
        Line("P2-42", "Premières cotisations supplémentaires admises", qpp.first_additional,
             "partie 2b : montant de la ligne 12, sans rajustement",
             refs=("5005-S8:P2-12", "5005-S8:P2-24")),
        Line("P2-46", "Deuxièmes cotisations supplémentaires admises", qpp.second_additional,
             "partie 2b : montant de la ligne 22, sans rajustement",
             refs=("5005-S8:P2-22", "5005-S8:P2-24")),
        Line("P2-47", "Déduction pour les cotisations bonifiées au RRQ sur un revenu d'emploi", qpp.enhanced,
             refs=("5005-S8:P2-42", "5005-S8:P2-46")),
    )}
    return f


def worksheet(tp: Taxpayer, params: dict, federal: Form, eligible_annuity: float) -> Form | None:
    """Feuille 5000-D1, grilles 23500, 25000 et 31400, seulement lorsqu'une grille s'applique.

    Les revenus PUGE, REEI, pensions étrangères et transferts directs ne sont pas encore
    des entrées : les lignes correspondantes ne sont pas créées. Les sous-totaux indiquent
    cette portée. La récupération d'AE précède celle de la PSV et des suppléments fédéraux.
    """
    tables = params["federal"]
    benefits = tp.benefits
    before = federal.amount("23400")
    ei = 0.0
    supplements = overpayment = 0.0
    if benefits is not None:
        supplements = benefits.federal_supplements
        overpayment = benefits.oas_overpayment_recovered
        if benefits.ei_regular and benefits.ei_repayment_exempt is False:
            table = tables["ei_repayment"]
            ei = table["rate"] * min(max(0.0, benefits.ei_regular - benefits.ei_repaid),
                                     max(0.0, before - table["threshold"]))
    oas = tables["oas_recovery"]
    ceiling = max(0.0, tp.oas_pension + supplements - overpayment)
    recovered = min(ceiling, max(0.0, before - ei - oas["threshold"]) * oas["rate"])
    pension = federal.amount("11500") + eligible_annuity
    if not (ei or recovered or pension or supplements):
        return None
    f = Form.from_parameters("5000-D1", params)
    if ei or recovered:
        f.add("23500-1", "Pension de la sécurité de la vieillesse", tp.oas_pension,
              refs=("T1:11300",))
        f.add("23500-2", "Versement net des suppléments fédéraux", supplements,
              refs=("T1:14600",) if "14600" in federal.lines else ())
        f.add("23500-3", "Ligne 1 plus ligne 2", tp.oas_pension + supplements,
              refs=("5000-D1:23500-1", "5000-D1:23500-2"))
        f.add("23500-4", "Paiement en trop de la PSV recouvré", overpayment,
              "case 20 du T4A(OAS), remboursement de trop-perçu")
        f.add("23500-5", "Ligne 3 moins ligne 4", ceiling, "minimum zéro",
              refs=("5000-D1:23500-3", "5000-D1:23500-4"))
        f.add("23500-6", "Revenu net avant rajustements", before, refs=("T1:23400",))
        f.add("23500-7", "Remboursement de prestations d'AE", ei,
              "T4E : 30 % du moindre de l'excédent du revenu net et de la case 15 moins la case 30; "
              "prestations spéciales et RQAP exclus; exemption confirmée par l'appelant",
              refs=("T1:23400",) + (("T1:11900",) if "11900" in federal.lines else ())
                   + (("T1:23200",) if "23200" in federal.lines else ()),
              params=("federal.ei_repayment.threshold", "federal.ei_repayment.rate"))
        f.add("23500-10", "Total des lignes 7 à 9", ei, "aucune PUGE ni REEI dans les entrées",
              refs=("5000-D1:23500-7",))
        f.add("23500-11", "Ligne 6 moins ligne 10", before - ei,
              refs=("5000-D1:23500-6", "5000-D1:23500-10"))
        f.add("23500-15", "Revenu net rajusté", before - ei, "aucun remboursement PUGE ou REEI",
              refs=("5000-D1:23500-11",))
        f.add("23500-16", "Montant de base de PSV", oas["threshold"],
              params=("federal.oas_recovery.threshold",))
        excess = f.add("23500-17", "Ligne 15 moins ligne 16", max(0.0, before - ei - oas["threshold"]),
                       "minimum zéro", refs=("5000-D1:23500-15", "5000-D1:23500-16"))
        f.add("23500-18", "Montant de la ligne 17 multiplié par 15 %", excess * oas["rate"],
              refs=("5000-D1:23500-17",), params=("federal.oas_recovery.rate",))
        f.add("23500-19", "Montant le moins élevé : ligne 5 ou ligne 18", recovered,
              refs=("5000-D1:23500-5", "5000-D1:23500-18"))
        f.add("23500-20", "Montant de la ligne 7", ei, refs=("5000-D1:23500-7",))
        f.add("23500-21", "Remboursement des prestations de programmes sociaux", recovered + ei,
              refs=("5000-D1:23500-19", "5000-D1:23500-20"))
    if supplements:
        f.add("25000-1", "Montant de la ligne 23400", max(0.0, before), "minimum zéro",
              refs=("T1:23400",))
        f.add("25000-5", "Ligne 1 moins ligne 4", max(0.0, before), "aucune PUGE ni REEI dans les entrées",
              refs=("5000-D1:25000-1",))
        f.add("25000-9", "Ligne 5 plus ligne 8", max(0.0, before), "aucun remboursement PUGE ni REEI; "
              "tableau spécial de la ligne 25000 lorsque ce résultat dépasse le seuil PSV",
              refs=("5000-D1:25000-5",), params=("federal.oas_recovery.threshold",))
    if pension:
        f.add("31400-1", "Montant de la ligne 11500", federal.amount("11500"), refs=("T1:11500",))
        f.add("31400-6", "Ligne 1 moins ligne 5", federal.amount("11500"),
              "pensions canadiennes admissibles, sans transfert direct", refs=("5000-D1:31400-1",))
        f.add("31400-7", "Paiements de rente de la ligne 12900", eligible_annuity,
              "65 ans et plus ou rente reçue en raison du décès du conjoint",
              refs=("T1:12900",), params=("federal.pension_amount.minimum_age_for_rrif",))
        f.add("31400-8", "Ligne 6 plus ligne 7", pension,
              refs=("5000-D1:31400-6", "5000-D1:31400-7"))
    return f
