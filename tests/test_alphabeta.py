import os

from minichess.gardner import JeuGardner
from minichess.echecs import JeuEchecs
from minichess.arene import jouer_partie
from minichess.joueurs import creer_joueur, JoueurAleatoire, JoueurAlphaBeta
from minichess.puzzles import charger_puzzles, resoudre

ICI = os.path.dirname(__file__)


def test_trouve_mat_en_1():
    jeu = JeuGardner.depuis_texte(["k....", "..K..", ".....", ".....", "....R"])
    coup = JoueurAlphaBeta().choisir_coup(jeu, 5000)
    assert jeu.coup_vers_texte(coup) == "e1a1"


def test_evite_le_piege_de_la_dame():
    # La dame d1 peut prendre le pion d4, mais il est protégé par le pion e5.
    #   5  k . . . p
    #   4  . . . p .
    #   3  . . . . .
    #   2  . . . . .
    #   1  K . . Q .
    jeu = JeuGardner.depuis_texte(["k...p", "...p.", ".....", ".....", "K..Q."])
    ab = JoueurAlphaBeta()
    coup = ab.choisir_coup(jeu, 5000)
    assert jeu.coup_vers_texte(coup) != "d1d4"
    assert ab.derniere_profondeur >= 2


def test_respecte_le_budget():
    for budget in (1, 10, 100, 3000):
        ab = JoueurAlphaBeta()
        coup = ab.choisir_coup(JeuGardner(), budget)
        assert coup in JeuGardner().coups_legaux()
        assert ab.positions_utilisees <= budget


def test_ablation_options():
    j = creer_joueur("alphabeta:quiescence=0,mvv_lva=0,tt=0")
    assert not j.quiescence and not j.mvv_lva and not j.tt
    assert j.choisir_coup(JeuGardner(), 500) in JeuGardner().coups_legaux()


def test_bat_le_joueur_aleatoire():
    score = 0
    for i in range(6):
        ab, al = JoueurAlphaBeta(), JoueurAleatoire(graine=i)
        blanc, noir = (ab, al) if i % 2 == 0 else (al, ab)
        r = jouer_partie(blanc, noir, JeuGardner(), budget=1000)["resultat"]
        score += (r + 1) / 2 if blanc is ab else (1 - r) / 2
    assert score >= 5


def test_resout_les_problemes_exemple():
    puzzles = charger_puzzles(os.path.join(ICI, "..", "donnees", "puzzles_exemple.csv"))
    assert len(puzzles) == 4
    for p in puzzles:
        assert resoudre(JoueurAlphaBeta(), p, 20000), p["PuzzleId"]


def test_fonctionne_sur_echecs_complets():
    jeu = JeuEchecs()
    coup = JoueurAlphaBeta().choisir_coup(jeu, 2000)
    assert coup in jeu.coups_legaux()
