"""Interface commune à tous les jeux (mini-échecs 5×5, échecs complets).

Contrat partagé entre la personne A (moteur, alpha-bêta) et la personne B (MCTS).
Tous les joueurs ne manipulent un jeu QUE via ces méthodes.

Conventions :
- `trait` vaut +1 si c'est aux blancs de jouer, -1 si c'est aux noirs.
- `resultat()` est donné du point de vue des BLANCS : +1, 0 ou -1.
- Les états sont immuables : `jouer(coup)` renvoie un NOUVEL état
  (pratique pour MCTS, aucun « annuler le coup » à gérer).

Budget de calcul (équité entre algorithmes) :
    1 unité de budget = 1 appel à `jouer()`.
Chaque implémentation incrémente `Jeu.compteur` dans `jouer()`. Un joueur mesure
ce qu'il a consommé avec `Jeu.compteur - debut`. Alpha-bêta et MCTS sont donc
comparés au même nombre de positions générées, indépendamment de la vitesse du code.
"""

from abc import ABC, abstractmethod


class Jeu(ABC):
    compteur = 0  # nombre total d'appels à jouer() (par processus)

    @property
    @abstractmethod
    def trait(self) -> int:
        """+1 si les blancs jouent, -1 si les noirs jouent."""

    @abstractmethod
    def coups_legaux(self) -> list:
        """Liste des coups légaux (vide si la partie est finie par mat/pat)."""

    @abstractmethod
    def jouer(self, coup) -> "Jeu":
        """Renvoie le nouvel état après `coup`. Doit faire `Jeu.compteur += 1`."""

    @abstractmethod
    def est_fini(self) -> bool:
        """Vrai si la partie est terminée (mat, pat, nulle, limite de coups)."""

    @abstractmethod
    def resultat(self) -> int:
        """+1 (blancs gagnent), 0 (nulle), -1 (noirs gagnent). Seulement si est_fini()."""

    @abstractmethod
    def materiel(self) -> int:
        """Matériel blancs - matériel noirs, en centipions (pion = 100)."""

    @abstractmethod
    def info_capture(self, coup):
        """(valeur_victime, valeur_attaquant) en centipions si `coup` est une capture, sinon None."""

    @abstractmethod
    def est_promotion(self, coup) -> bool:
        """Vrai si `coup` promeut un pion."""

    @abstractmethod
    def en_echec(self) -> bool:
        """Vrai si le roi du joueur au trait est en échec."""

    @abstractmethod
    def cle(self):
        """Clé hachable identifiant la position (pour tables de transposition)."""

    @abstractmethod
    def coup_vers_texte(self, coup) -> str:
        """Notation UCI, ex. 'a2a3' ou 'b4b5q'."""

    @abstractmethod
    def texte_vers_coup(self, texte: str):
        """Inverse de coup_vers_texte."""
