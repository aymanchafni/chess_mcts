"""Fonctions d'évaluation, partagées par alpha-bêta ET par MCTS (variante M2).

Utiliser la même évaluation dans les deux familles rend la comparaison équitable :
la différence de force vient de l'algorithme de recherche, pas de l'heuristique.
"""

MAT = 100_000  # score d'un mat (en centipions), bien au-delà de tout matériel


def evaluer(jeu) -> int:
    """Matériel du point de vue du joueur AU TRAIT (convention négamax), en centipions."""
    return jeu.trait * jeu.materiel()


def score_terminal(jeu, ply: int) -> int:
    """Score d'une position finie, du point de vue du joueur au trait.
    Un mat proche vaut plus qu'un mat lointain (MAT - ply)."""
    r = jeu.resultat()
    if r == 0:
        return 0
    return (MAT - ply) * r * jeu.trait


def proba_victoire(score_cp: float, echelle: float = 400.0) -> float:
    """Convertit un avantage en centipions en « chance de gagner » dans [0, 1].
    0 -> 0,50 ; +200 -> 0,76 ; -300 -> 0,15.  (Utile pour l'arrêt précoce de MCTS, M2.)"""
    return 1.0 / (1.0 + 10.0 ** (-score_cp / echelle))


def score_mvv_lva(jeu, coup) -> int:
    """Ordre des coups « victime la plus chère, attaquant le moins cher ».
    Plus le score est grand, plus le coup est examiné tôt."""
    s = 0
    info = jeu.info_capture(coup)
    if info is not None:
        victime, attaquant = info
        s += 10_000 + 10 * victime - attaquant
    if jeu.est_promotion(coup):
        s += 9_000
    return s
