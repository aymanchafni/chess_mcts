"""Registre des joueurs : crée un joueur à partir d'une chaîne, ex.

    "aleatoire"
    "alphabeta"
    "alphabeta:quiescence=0,mvv_lva=0"
    "uct:c=1.4,politique=captures,coupure=4,solver=1"
    "M2"                      (préréglage, voir PRESETS)

Les chaînes passent facilement entre processus (tournois en parallèle) et en ligne
de commande.
"""

from .base import Joueur, JoueurAleatoire
from .alphabeta import JoueurAlphaBeta
from .mcts import JoueurUCT

REGISTRE = {
    "aleatoire": JoueurAleatoire,
    "alphabeta": JoueurAlphaBeta,
    "uct": JoueurUCT,
}

# Les méthodes du projet, sous leurs noms du rapport.
PRESETS = {
    "B1": "alphabeta",
    "B2": "uct",
    "M1": "uct:politique=captures,eps=0.8",
    "M2": "uct:coupure=4",
    "M3": "uct:solver=1",
    "M4": "uct:minimax=1",
    "M5": "uct:biais=1.0",
    "M1+M2+M3": "uct:politique=captures,eps=0.8,coupure=4,solver=1",
    # Méthode proposée : aucune simulation (feuille évaluée directement), exploration réduite.
    "M6": "uct:c=0.5,politique=captures,coupure=0,solver=1",
}


def _convertir(valeur: str):
    for conv in (int, float):
        try:
            return conv(valeur)
        except ValueError:
            pass
    if valeur.lower() in ("true", "vrai", "oui"):
        return True
    if valeur.lower() in ("false", "faux", "non"):
        return False
    return valeur


def creer_joueur(spec: str) -> Joueur:
    """Le nom affiché du joueur est `spec` tel quel (ex. « M2 »)."""
    vraie_spec = PRESETS.get(spec, spec)
    nom, _, params = vraie_spec.partition(":")
    kwargs = {}
    if params:
        for paire in params.split(","):
            cle, _, val = paire.partition("=")
            kwargs[cle.strip()] = _convertir(val.strip())
    if nom not in REGISTRE:
        raise ValueError(f"Joueur inconnu : {nom!r}. Disponibles : {sorted(REGISTRE)} "
                         f"ou préréglages {sorted(PRESETS)}")
    joueur = REGISTRE[nom](**kwargs)
    joueur.nom = spec
    return joueur
