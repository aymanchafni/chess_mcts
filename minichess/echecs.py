"""Adaptateur : échecs complets (8×8) via python-chess, avec la même interface `Jeu`.

Sert à deux choses :
- évaluer les joueurs sur les problèmes tactiques Lichess (puzzles.py) ;
- permettre à la personne B de tester son MCTS sur les vrais échecs.

Note : pour rester rapide, l'historique n'est pas copié d'un état à l'autre,
donc la répétition de position n'est pas détectée (sans importance pour les problèmes).
"""

import chess
import chess.polyglot

from .jeu import Jeu

VALEURS = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300,
           chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}


class JeuEchecs(Jeu):
    LIMITE_DEMI_COUPS = 400

    __slots__ = ("board", "demi_coups", "_coups", "_issue")

    def __init__(self, board=None, demi_coups=0):
        self.board = board if board is not None else chess.Board()
        self.demi_coups = demi_coups
        self._coups = None
        self._issue = False  # False = pas encore calculé

    @classmethod
    def depuis_fen(cls, fen):
        return cls(chess.Board(fen))

    @property
    def trait(self):
        return 1 if self.board.turn == chess.WHITE else -1

    def coups_legaux(self):
        if self._coups is None:
            self._coups = list(self.board.legal_moves)
        return self._coups

    def jouer(self, coup):
        Jeu.compteur += 1
        b = self.board.copy(stack=False)
        b.push(coup)
        return JeuEchecs(b, self.demi_coups + 1)

    def _outcome(self):
        if self._issue is False:
            self._issue = self.board.outcome(claim_draw=False)
        return self._issue

    def est_fini(self):
        return self._outcome() is not None or self.demi_coups >= self.LIMITE_DEMI_COUPS

    def resultat(self):
        issue = self._outcome()
        if issue is None or issue.winner is None:
            return 0
        return 1 if issue.winner == chess.WHITE else -1

    def materiel(self):
        total = 0
        for piece in self.board.piece_map().values():
            v = VALEURS[piece.piece_type]
            total += v if piece.color == chess.WHITE else -v
        return total

    def info_capture(self, coup):
        if not self.board.is_capture(coup):
            return None
        if self.board.is_en_passant(coup):
            victime = chess.PAWN
        else:
            victime = self.board.piece_type_at(coup.to_square)
        return VALEURS[victime], VALEURS[self.board.piece_type_at(coup.from_square)]

    def est_promotion(self, coup):
        return coup.promotion is not None

    def en_echec(self):
        return self.board.is_check()

    def cle(self):
        return chess.polyglot.zobrist_hash(self.board)

    def coup_vers_texte(self, coup):
        return coup.uci()

    def texte_vers_coup(self, texte):
        return chess.Move.from_uci(texte)

    def __str__(self):
        return str(self.board)
