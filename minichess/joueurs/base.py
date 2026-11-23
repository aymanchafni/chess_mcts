"""Interface commune des joueurs. La personne B fait hériter ses MCTS de cette classe."""

import random
from abc import ABC, abstractmethod


class Joueur(ABC):
    nom = "joueur"

    def nouvelle_partie(self):
        """Appelé au début de chaque partie (ex. vider un arbre MCTS réutilisé)."""

    @abstractmethod
    def choisir_coup(self, jeu, budget: int):
        """Renvoie un coup légal de `jeu`.
        `budget` = nombre maximal d'appels à jeu.jouer() pour ce coup (voir jeu.py)."""

    def __repr__(self):
        return self.nom


class JoueurAleatoire(Joueur):
    """Joue un coup légal au hasard. Sert de référence la plus faible."""

    def __init__(self, graine=None):
        self.rng = random.Random(graine)
        self.nom = "aleatoire"

    def choisir_coup(self, jeu, budget):
        return self.rng.choice(jeu.coups_legaux())
