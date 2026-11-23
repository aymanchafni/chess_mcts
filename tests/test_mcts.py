import pytest

from minichess.gardner import JeuGardner
from minichess.echecs import JeuEchecs
from minichess.arene import jouer_partie
from minichess.joueurs import creer_joueur, PRESETS, JoueurAleatoire
from minichess.joueurs.mcts import JoueurUCT

MAT_EN_1 = ["k....", "..K..", ".....", ".....", "....R"]   # Ta1#
PIEGE = ["k...p", "...p.", ".....", ".....", "K..Q."]       # Dxd4?? exd4


@pytest.mark.parametrize("preset", [p for p in PRESETS if p != "B1"])
def test_chaque_methode_joue_un_coup_legal_dans_le_budget(preset):
    j = creer_joueur(preset)
    jeu = JeuGardner()
    for budget in (5, 300, 3000):
        coup = j.choisir_coup(jeu, budget)
        assert coup in jeu.coups_legaux()
        assert j.positions_utilisees <= budget


@pytest.mark.parametrize("preset", [p for p in PRESETS if p != "B1"])
def test_trouve_le_mat_en_1(preset):
    jeu = JeuGardner.depuis_texte(MAT_EN_1)
    assert jeu.coup_vers_texte(creer_joueur(preset).choisir_coup(jeu, 5000)) == "e1a1"


def test_solver_prouve_le_mat_et_s_arrete():
    jeu = JeuGardner.depuis_texte(MAT_EN_1)
    j = JoueurUCT(solver=True, graine=1)
    j.choisir_coup(jeu, 100_000)
    assert j.racine_resolue
    assert j.positions_utilisees < 100_000   # s'arrête dès que c'est prouvé


def test_solver_evite_un_coup_qui_permet_le_mat():
    # Mat du couloir : si la tour blanche quitte la 1re rangée, ...De1 est mat
    # (roi a1 enfermé par ses pions a2, b2). Le Solver doit éviter ces coups.
    jeu = JeuGardner.depuis_texte(["k...q", ".....", ".....", "PP...", "K...R"])
    j = JoueurUCT(solver=True, graine=0)
    coup = j.choisir_coup(jeu, 20_000)
    apres = jeu.jouer(coup)
    # après notre coup, l'adversaire ne doit pas avoir de mat en 1
    for r in apres.coups_legaux():
        fin = apres.jouer(r)
        assert not (fin.est_fini() and fin.resultat() == -1), jeu.coup_vers_texte(coup)


def test_coupure_evite_le_piege():
    jeu = JeuGardner.depuis_texte(PIEGE)
    for g in range(5):
        coup = JoueurUCT(coupure=4, graine=g).choisir_coup(jeu, 5000)
        assert jeu.coup_vers_texte(coup) != "d1d4"


def test_biais_progressif_favorise_les_captures():
    from minichess.joueurs.mcts import valeur_heuristique
    jeu = JeuGardner.depuis_texte(PIEGE)
    assert valeur_heuristique(jeu, jeu.texte_vers_coup("d1d4")) > 0
    assert valeur_heuristique(jeu, jeu.texte_vers_coup("a1b2")) == 0


def test_m2_bat_le_joueur_aleatoire():
    score = 0
    for i in range(4):
        m, al = creer_joueur("M2"), JoueurAleatoire(graine=i)
        blanc, noir = (m, al) if i % 2 == 0 else (al, m)
        r = jouer_partie(blanc, noir, JeuGardner(), budget=1000)["resultat"]
        score += (r + 1) / 2 if blanc is m else (1 - r) / 2
    assert score >= 3


def test_fonctionne_sur_echecs_complets():
    jeu = JeuEchecs()
    j = creer_joueur("M1+M2+M3")
    assert j.choisir_coup(jeu, 500) in jeu.coups_legaux()
