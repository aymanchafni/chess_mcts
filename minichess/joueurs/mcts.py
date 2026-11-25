"""Monte Carlo Tree Search (UCT) et ses variantes.  [Personne B]

Un seul joueur paramétrable couvre toutes les méthodes du projet :

    B2  UCT pur                    JoueurUCT()
    M1  simulations guidées        JoueurUCT(politique="captures", eps=0.8)
    M2  arrêt précoce + évaluation JoueurUCT(coupure=4)
    M3  MCTS-Solver                JoueurUCT(solver=True)
    M4  hybride MCTS-minimax       JoueurUCT(minimax=1)
    M5  biais progressif           JoueurUCT(biais=1.0)

Les options se combinent librement, ex. JoueurUCT(politique="captures", coupure=4, solver=True).

Une itération = sélection -> expansion -> évaluation (simulation) -> rétropropagation.
Le budget (appels à jeu.jouer()) est vérifié avant CHAQUE coup joué, simulations
comprises : MCTS et alpha-bêta reçoivent exactement la même quantité de calcul.

Convention : dans chaque nœud, `w` et `preuve` sont exprimés du point de vue du joueur
qui a joué le coup MENANT à ce nœud (c'est lui qui choisit ce nœud à la sélection).
Récompenses dans [0, 1] : 1 = victoire, 0,5 = nulle, 0 = défaite.

Références :
- Kocsis & Szepesvári (2006), UCT.
- Winands, Björnsson & Saito (2008), MCTS-Solver.
- Chaslot et al. (2008), biais progressif.
- Baier & Winands (2018), hybrides MCTS-minimax avec évaluations d'états.
"""

import math
import random

from ..evaluation import proba_victoire, score_mvv_lva
from ..jeu import Jeu
from .alphabeta import JoueurAlphaBeta, BudgetEpuise
from .base import Joueur


class Noeud:
    __slots__ = ("jeu", "parent", "coup", "enfants", "non_essayes",
                 "n", "w", "preuve", "terminal", "h")

    def __init__(self, jeu, parent=None, coup=None, h=0.0):
        self.jeu = jeu
        self.parent = parent
        self.coup = coup
        self.enfants = []
        self.non_essayes = None   # coups pas encore développés (rempli à la 1re visite)
        self.n = 0                # visites
        self.w = 0.0              # somme des récompenses (point de vue du joueur arrivant ici)
        self.preuve = None        # MCTS-Solver : +1 gagné, 0 nul, -1 perdu (même point de vue)
        self.terminal = jeu.est_fini()
        self.h = h                # valeur heuristique du coup (biais progressif)


def valeur_heuristique(jeu, coup):
    """Intérêt a priori d'un coup dans [0, 1] : valeur de la pièce prise, promotions."""
    h = 0.0
    info = jeu.info_capture(coup)
    if info is not None:
        h += info[0] / 900          # prendre une dame = 1, un pion = 0,11
    if jeu.est_promotion(coup):
        h += 0.8
    return min(h, 1.0)


class JoueurUCT(Joueur):
    def __init__(self, c=1.4, politique="aleatoire", eps=0.8, coupure=None,
                 solver=False, minimax=None, biais=0.0, graine=None, nom=None):
        if politique not in ("aleatoire", "captures"):
            raise ValueError("politique = 'aleatoire' ou 'captures'")
        self.c = c
        self.politique = politique
        self.eps = eps
        self.coupure = coupure      # None = simulation jusqu'à la fin de la partie
        self.solver = bool(solver)
        self.minimax = minimax      # profondeur du mini alpha-bêta aux feuilles (None = non)
        self.biais = biais
        self.rng = random.Random(graine)
        self.nom = nom or "uct"
        self._ab = JoueurAlphaBeta(tt=False) if minimax is not None else None
        # statistiques du dernier coup
        self.iterations = 0
        self.positions_utilisees = 0
        self.racine_resolue = False

    # ------------------------------------------------------------------ racine
    def choisir_coup(self, jeu, budget):
        coups = jeu.coups_legaux()
        if len(coups) == 1:
            return coups[0]
        self.debut, self.budget = Jeu.compteur, budget
        racine = Noeud(jeu)
        self.iterations = 0
        # `iterations < budget` : garde-fou quand l'arbre entier ne mène qu'à des fins de partie
        # (ex. tous les coups atteignent la limite de demi-coups) et qu'une itération ne coûte rien.
        while Jeu.compteur - self.debut < budget and self.iterations < budget:
            if self.solver and racine.preuve is not None:
                break                      # position résolue : inutile de continuer
            try:
                self._iteration(racine)
            except BudgetEpuise:
                break                      # itération inachevée : rien n'est rétropropagé
            self.iterations += 1
        self.positions_utilisees = Jeu.compteur - self.debut
        self.racine_resolue = racine.preuve is not None
        return self._coup_final(racine, coups)

    def _coup_final(self, racine, coups):
        if not racine.enfants:
            return coups[0]
        if self.solver:
            gagnants = [e for e in racine.enfants if e.preuve == 1]
            if gagnants:
                return gagnants[0].coup
            surs = [e for e in racine.enfants if e.preuve != -1]
            candidats = surs or racine.enfants
        else:
            candidats = racine.enfants
        # « enfant robuste » : le plus visité (départage par la moyenne)
        return max(candidats, key=lambda e: (e.n, e.w / max(e.n, 1))).coup

    # --------------------------------------------------------------- itération
    def _iteration(self, racine):
        noeud = racine
        # 1. Sélection : descendre tant que le nœud est entièrement développé
        while (not noeud.terminal and noeud.preuve is None
               and noeud.non_essayes == [] and noeud.enfants):
            noeud = self._selectionner(noeud)

        # 2. Expansion : ajouter UN nouveau coup
        if not noeud.terminal and noeud.preuve is None:
            if noeud.non_essayes is None:
                noeud.non_essayes = list(noeud.jeu.coups_legaux())
                self.rng.shuffle(noeud.non_essayes)
            coup = noeud.non_essayes.pop()
            h = valeur_heuristique(noeud.jeu, coup) if self.biais else 0.0
            enfant = Noeud(self._jouer(noeud.jeu, coup), noeud, coup, h)
            noeud.enfants.append(enfant)
            noeud = enfant

        # 3. Évaluation (point de vue du joueur qui a joué le coup menant à `noeud`)
        joueur = -noeud.jeu.trait
        if noeud.terminal:
            r = noeud.jeu.resultat() * joueur          # +1 / 0 / -1 pour ce joueur
            if self.solver:
                noeud.preuve = r
            v = (r + 1) / 2
        elif noeud.preuve is not None:
            v = (noeud.preuve + 1) / 2
        else:
            p_blancs = self._evaluer(noeud.jeu)
            v = p_blancs if joueur == 1 else 1 - p_blancs

        # 4. Rétropropagation (la récompense change de camp à chaque niveau)
        while noeud is not None:
            noeud.n += 1
            noeud.w += v
            if self.solver and noeud.parent is not None:
                self._maj_preuve(noeud.parent)
            v = 1 - v
            noeud = noeud.parent

    def _selectionner(self, noeud):
        enfants = noeud.enfants
        if self.solver:
            # ne jamais redescendre dans un coup prouvé perdant (s'il existe une alternative)
            enfants = [e for e in enfants if e.preuve != -1] or enfants
        log_n = math.log(noeud.n)
        meilleur, meilleur_score = None, -math.inf
        for e in enfants:
            score = e.w / e.n + self.c * math.sqrt(log_n / e.n)
            if self.biais:
                score += self.biais * e.h / (e.n + 1)  # s'efface quand e.n grandit
            if score > meilleur_score:
                meilleur, meilleur_score = e, score
        return meilleur

    def _maj_preuve(self, p):
        """MCTS-Solver : remonte les valeurs prouvées (minimax sur les nœuds résolus)."""
        if p.preuve is not None:
            return
        # Un enfant gagnant pour le joueur au trait en p => p est perdu pour celui qui y est arrivé.
        if any(e.preuve == 1 for e in p.enfants):
            p.preuve = -1
        elif p.non_essayes == [] and all(e.preuve is not None for e in p.enfants):
            p.preuve = -max(e.preuve for e in p.enfants)

    # -------------------------------------------------------------- évaluation
    def _jouer(self, jeu, coup):
        if Jeu.compteur - self.debut >= self.budget:
            raise BudgetEpuise()
        return jeu.jouer(coup)

    def _evaluer(self, jeu):
        """Probabilité de victoire des BLANCS, estimée depuis `jeu`."""
        if self.minimax is not None:                                   # M4
            restant = self.budget - (Jeu.compteur - self.debut)
            score = self._ab.evaluer_position(jeu, self.minimax, restant)
            p = proba_victoire(score)
            return p if jeu.trait == 1 else 1 - p
        return self._simuler(jeu)

    def _simuler(self, jeu):
        d = 0
        while not jeu.est_fini():
            if self.coupure is not None and d >= self.coupure:          # M2
                return proba_victoire(jeu.materiel())
            jeu = self._jouer(jeu, self._coup_simulation(jeu))
            d += 1
        return (jeu.resultat() + 1) / 2

    def _coup_simulation(self, jeu):
        coups = jeu.coups_legaux()
        if self.politique == "captures" and self.rng.random() < self.eps:  # M1
            notes = [(score_mvv_lva(jeu, c), c) for c in coups]
            meilleure = max(s for s, _ in notes)
            if meilleure > 0:
                return self.rng.choice([c for s, c in notes if s == meilleure])
        return self.rng.choice(coups)
