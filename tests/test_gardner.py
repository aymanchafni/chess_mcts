"""Tests des règles du 5×5.

Test clé : comparaison avec python-chess. On plonge la position 5×5 dans le coin
d'un échiquier 8×8 vide (colonnes a-e, rangées 1-5), on demande les coups légaux
à python-chess et on ne garde que ceux qui restent dans le 5×5 (sans double pas).
C'est une vérification indépendante de notre générateur de coups.
"""

import random

import chess
import pytest

from minichess.gardner import JeuGardner, N, LETTRES, ROI, DAME, CAVALIER
from minichess.jeu import Jeu


# --------------------------------------------------------------- oracle 8×8
def vers_board(jeu):
    board = chess.Board(None)  # échiquier vide
    for case, p in enumerate(jeu.plateau):
        if p:
            r, c = divmod(case, N)
            board.set_piece_at(chess.square(c, r), chess.Piece(abs(p), p > 0))
    board.turn = jeu.trait == 1
    return board


def dans_5x5(sq):
    return chess.square_file(sq) < N and chess.square_rank(sq) < N


def coups_oracle(board):
    res = set()
    for m in board.legal_moves:
        if not dans_5x5(m.to_square):
            continue
        piece = board.piece_type_at(m.from_square)
        if piece == chess.PAWN and abs(chess.square_rank(m.to_square) - chess.square_rank(m.from_square)) == 2:
            continue  # pas de double pas en Gardner
        res.add((m.from_square, m.to_square))
    return res


def nos_coups(jeu):
    def sq(c):
        r, col = divmod(c, N)
        return chess.square(col, r)
    return {(sq(d), sq(a)) for d, a, _ in jeu.coups_legaux()}


def perft(jeu, prof):
    if prof == 0:
        return 1
    return sum(perft(jeu.jouer(c), prof - 1) for c in jeu.coups_legaux())


def perft_oracle(board, prof):
    if prof == 0:
        return 1
    total = 0
    for m in list(board.legal_moves):
        if not dans_5x5(m.to_square):
            continue
        if board.piece_type_at(m.from_square) == chess.PAWN and \
                abs(chess.square_rank(m.to_square) - chess.square_rank(m.from_square)) == 2:
            continue
        board.push(m)
        total += perft_oracle(board, prof - 1)
        board.pop()
    return total


# --------------------------------------------------------------------- tests
def test_position_initiale_7_coups():
    jeu = JeuGardner()
    assert len(jeu.coups_legaux()) == 7  # 5 pions + 2 coups de cavalier
    assert jeu.materiel() == 0
    assert not jeu.est_fini()


@pytest.mark.parametrize("prof", [1, 2, 3, 4])
def test_perft_identique_a_python_chess(prof):
    # Jusqu'à 4 demi-coups, aucune promotion n'est possible : comptes identiques.
    assert perft(JeuGardner(), prof) == perft_oracle(vers_board(JeuGardner()), prof)


def test_parties_aleatoires_identiques_a_python_chess():
    rng = random.Random(42)
    positions = 0
    for _ in range(300):
        jeu = JeuGardner()
        while not jeu.est_fini():
            assert nos_coups(jeu) == coups_oracle(vers_board(jeu)), f"\n{jeu}"
            assert jeu.en_echec() == vers_board(jeu).is_check()
            positions += 1
            jeu = jeu.jouer(rng.choice(jeu.coups_legaux()))
        # Mat / pat : python-chess doit être d'accord (si aucun coup ne sort du 5×5).
        if not jeu.coups_legaux():
            b = vers_board(jeu)
            if not coups_oracle(b):
                assert jeu.en_echec() == b.is_check()
    assert positions > 5000


def test_promotion():
    jeu = JeuGardner.depuis_texte(["....k", "P....", ".....", ".....", "K...."])
    promos = [c for c in jeu.coups_legaux() if c[2]]
    assert len(promos) == 4
    apres = jeu.jouer(jeu.texte_vers_coup("a4a5q"))
    assert apres.plateau[4 * N + 0] == DAME
    sous_promo = jeu.jouer(jeu.texte_vers_coup("a4a5n"))
    assert sous_promo.plateau[4 * N + 0] == CAVALIER


def test_mat():
    # Roi blanc c4 + tour : Ta1 est mat (le roi noir a5 n'a plus de case).
    jeu = JeuGardner.depuis_texte(["k....", "..K..", ".....", ".....", "....R"])
    apres = jeu.jouer(jeu.texte_vers_coup("e1a1"))
    assert apres.en_echec() and apres.est_fini() and apres.resultat() == 1


def test_pat():
    # Noirs au trait, roi a5 pas en échec mais aucun coup : nulle.
    jeu = JeuGardner.depuis_texte(["k....", "..Q..", ".K...", ".....", "....."], trait=-1)
    assert not jeu.en_echec()
    assert jeu.coups_legaux() == []
    assert jeu.est_fini() and jeu.resultat() == 0


def test_materiel_insuffisant():
    jeu = JeuGardner.depuis_texte(["k....", ".....", "..N..", ".....", "....K"])
    assert jeu.est_fini() and jeu.resultat() == 0


def test_triple_repetition():
    jeu = JeuGardner.depuis_texte(["k...r", ".....", ".....", ".....", "R...K"])
    aller_retour = ["a1b1", "a5b5", "b1a1", "b5a5"]
    for _ in range(2):
        for t in aller_retour:
            assert not jeu.est_fini()
            jeu = jeu.jouer(jeu.texte_vers_coup(t))
    assert jeu.est_fini() and jeu.resultat() == 0  # 3e apparition de la position


def test_notation_aller_retour():
    jeu = JeuGardner()
    for c in jeu.coups_legaux():
        assert jeu.texte_vers_coup(jeu.coup_vers_texte(c)) == c


def test_compteur_budget():
    jeu, avant = JeuGardner(), Jeu.compteur
    for c in jeu.coups_legaux():
        jeu.jouer(c)
    assert Jeu.compteur - avant == 7   # coups_legaux() ne consomme pas de budget
