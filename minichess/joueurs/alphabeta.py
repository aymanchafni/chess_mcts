"""Joueur alpha-bêta (référence B1).

- Négamax avec élagage alpha-bêta
- Approfondissement itératif : profondeur 1, 2, 3, ... jusqu'à épuisement du budget
- Recherche de quiescence : aux feuilles, on continue tant qu'il y a des captures
  (évite « l'effet d'horizon » : s'arrêter juste avant que l'adversaire reprenne)
- Ordre des coups : meilleur coup de l'itération précédente / table, puis MVV-LVA
- Table de transposition légère : ne mémorise que le meilleur coup par position
  (sert à l'ordre des coups ; aucun risque d'erreur avec les répétitions)

Chaque option peut être désactivée pour l'ablation :
    JoueurAlphaBeta(quiescence=False, mvv_lva=False, tt=False)
"""

from ..evaluation import evaluer, score_terminal, score_mvv_lva, MAT
from ..jeu import Jeu
from .base import Joueur

INF = 10 * MAT


class BudgetEpuise(Exception):
    def __init__(self, meilleur=None):
        super().__init__()
        self.meilleur = meilleur


class JoueurAlphaBeta(Joueur):
    def __init__(self, quiescence=True, mvv_lva=True, tt=True,
                 prof_max=64, prof_quiescence=8, evaluation=evaluer, nom=None):
        self.quiescence = quiescence
        self.mvv_lva = mvv_lva
        self.tt = tt
        self.prof_max = prof_max
        self.prof_quiescence = prof_quiescence
        self.evaluation = evaluation
        self.nom = nom or "alphabeta" + ("" if quiescence else "-noqs") + \
            ("" if mvv_lva else "-nommvlva") + ("" if tt else "-nott")
        self.table = {}
        # statistiques du dernier coup (pour le rapport)
        self.derniere_profondeur = 0
        self.dernier_score = 0
        self.positions_utilisees = 0

    def nouvelle_partie(self):
        self.table = {}

    # ------------------------------------------------------------------ racine
    def choisir_coup(self, jeu, budget):
        coups = jeu.coups_legaux()
        self.debut, self.budget = Jeu.compteur, budget
        if len(self.table) > 500_000:
            self.table.clear()
        meilleur = self._ordonner(jeu, coups)[0]
        self.derniere_profondeur, self.dernier_score = 0, 0
        if len(coups) > 1:
            for prof in range(1, self.prof_max + 1):
                try:
                    score, coup = self._racine(jeu, prof, meilleur)
                except BudgetEpuise as e:
                    if e.meilleur is not None:   # itération partielle mais exploitable
                        meilleur = e.meilleur
                    break
                meilleur = coup
                self.derniere_profondeur, self.dernier_score = prof, score
                if abs(score) >= MAT - 1000:     # mat trouvé : inutile de chercher plus loin
                    break
        self.positions_utilisees = Jeu.compteur - self.debut
        return meilleur

    def _racine(self, jeu, prof, premier):
        alpha, beta = -INF, INF
        meilleur, best = None, -INF
        for coup in self._ordonner(jeu, jeu.coups_legaux(), premier):
            try:
                enfant = self._jouer(jeu, coup)
                score = -self._negamax(enfant, prof - 1, -beta, -alpha, 1)
            except BudgetEpuise:
                # Le premier coup (meilleur de l'itération précédente) a été évalué
                # exactement ; tout coup ensuite jugé meilleur l'est vraiment.
                raise BudgetEpuise(meilleur)
            if score > best:
                best, meilleur = score, coup
            alpha = max(alpha, score)
        return best, meilleur

    def evaluer_position(self, jeu, prof, budget):
        """Score négamax (point de vue du joueur au trait) d'une position, à profondeur `prof`
        (+ quiescence). Utilisé par les hybrides MCTS-minimax (M4).
        Lève BudgetEpuise si `budget` appels à jouer() ne suffisent pas."""
        self.debut, self.budget = Jeu.compteur, budget
        return self._negamax(jeu, prof, -INF, INF, 0)

    # ---------------------------------------------------------------- recherche
    def _jouer(self, jeu, coup):
        if Jeu.compteur - self.debut >= self.budget:
            raise BudgetEpuise()
        return jeu.jouer(coup)

    def _negamax(self, jeu, prof, alpha, beta, ply):
        if jeu.est_fini():
            return score_terminal(jeu, ply)
        if prof <= 0:
            if self.quiescence:
                return self._quiescence(jeu, alpha, beta, ply, 0)
            return self.evaluation(jeu)

        cle = jeu.cle() if self.tt else None
        coups = self._ordonner(jeu, jeu.coups_legaux(), self.table.get(cle) if self.tt else None)
        best, best_coup = -INF, None
        for coup in coups:
            score = -self._negamax(self._jouer(jeu, coup), prof - 1, -beta, -alpha, ply + 1)
            if score > best:
                best, best_coup = score, coup
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break  # coupure : l'adversaire n'autorisera jamais cette ligne
        if self.tt:
            self.table[cle] = best_coup
        return best

    def _quiescence(self, jeu, alpha, beta, ply, pq):
        if jeu.est_fini():
            return score_terminal(jeu, ply)
        if jeu.en_echec():
            # En échec, « ne rien faire » n'existe pas : on examine toutes les parades.
            if pq >= self.prof_quiescence:
                return self.evaluation(jeu)
            best = -INF
            coups = jeu.coups_legaux()
        else:
            best = self.evaluation(jeu)          # « stand pat » : on peut s'arrêter là
            if best >= beta or pq >= self.prof_quiescence:
                return best
            alpha = max(alpha, best)
            coups = [c for c in jeu.coups_legaux()
                     if jeu.info_capture(c) is not None or jeu.est_promotion(c)]
        for coup in self._ordonner(jeu, coups):
            score = -self._quiescence(self._jouer(jeu, coup), -beta, -alpha, ply + 1, pq + 1)
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break
        return best

    def _ordonner(self, jeu, coups, prioritaire=None):
        if self.mvv_lva:
            coups = sorted(coups, key=lambda c: -score_mvv_lva(jeu, c))
        else:
            coups = list(coups)
        if prioritaire is not None and prioritaire in coups:
            coups.remove(prioritaire)
            coups.insert(0, prioritaire)
        return coups
