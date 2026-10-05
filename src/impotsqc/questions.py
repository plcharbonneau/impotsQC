# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pier-Luc Charbonneau
"""Questions à poser avant de calculer une déclaration, sans interaction dans la librairie."""

from __future__ import annotations

from .model import Taxpayer

_SPOUSE_SOURCE = "https://www.revenuquebec.ca/fr/definitions/conjointe-ou-conjoint-au-31-decembre/"
_DRUG_SOURCE = ("https://www.revenuquebec.ca/fr/citoyens/declaration-de-revenus/"
                "produire-votre-declaration-de-revenus/comment-remplir-votre-declaration-de-revenus/"
                "aide-par-ligne/400-a-447-impot-et-cotisations/ligne-447/")


class MissingInformationError(ValueError):
    """Calcul bloqué; `questions` associe les champs manquants aux questions à poser."""

    def __init__(self, questions: dict[str, str]) -> None:
        """Conserve les questions pour le script ou l'agent appelant."""
        self.questions = dict(questions)
        super().__init__("Renseignements requis avant le calcul : " + "; ".join(questions.values()))

    def to_dict(self) -> dict:
        """Erreur sérialisable en JSON, avec les clés d'entrée attendues et leurs questions."""
        return {"error": "missing_information", "questions": dict(self.questions)}


def required_questions(taxpayer: Taxpayer) -> dict[str, str]:
    """Rend les questions encore nécessaires; un dictionnaire vide autorise le calcul.

    Aucun statut n'est déduit du revenu, de l'âge ou de `lives_alone`. Les enfants admissibles
    sont demandés seulement si la couverture n'exempte pas déjà les douze mois de l'année.
    """
    questions = {}
    if taxpayer.has_spouse is None:
        questions["has_spouse"] = (
            f"Aviez-vous un conjoint fiscal au 31 décembre {taxpayer.year}, au sens de Revenu Québec ? "
            "Répondez True ou False, indépendamment du fait de vivre seul : mariage, union civile "
            "ou union de fait admissible; tenir compte des règles de séparation de 90 jours et de décès. "
            + _SPOUSE_SOURCE)
    if taxpayer.has_spouse is True and taxpayer.spouse_net_income is None:
        questions["spouse_net_income"] = (
            f"Quel est le revenu net de votre conjoint pour {taxpayer.year} au Québec "
            "(ligne 275 du TP-1), y compris s'il est de zéro ?")
    if taxpayer.drug_plan_exempt_months is None:
        questions["drug_plan_exempt_months"] = (
            f"Pour quels mois de {taxpayer.year} êtes-vous exempté de cotisation RAMQ : "
            "assurance médicaments privée de base (la vôtre, celle du conjoint ou d'un parent), "
            "ou autre exemption confirmée selon l'annexe K et le guide ? "
            "Une journée admissible suffit pour exempter le mois. Indiquez les mois de 1 à 12; "
            "[] confirme aucune exemption, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] confirme "
            "une exemption toute l'année. Une assurance complémentaire seule ne suffit pas. "
            "Les exemptions SRG doivent être vérifiées selon le guide. " + _DRUG_SOURCE)
    months = taxpayer.drug_plan_exempt_months
    if (months is None or len(months) < 12) and taxpayer.drug_plan_dependent_children is None:
        questions["drug_plan_dependent_children"] = (
            f"Combien d'enfants à charge admissibles à l'annexe K aviez-vous en {taxpayer.year} ? "
            "Confirmez 0 s'il n'y en a aucun; utilisez la définition du guide à la ligne 447 "
            "(les critères ne sont pas simplement le nombre d'enfants du ménage). " + _DRUG_SOURCE)
    return questions
