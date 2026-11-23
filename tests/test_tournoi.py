import pytest

from minichess.tournoi import elo_depuis_score, statistiques, lancer_tournoi, resumer
from minichess.arene import generer_ouvertures


def test_elo():
    assert elo_depuis_score(0.5) == pytest.approx(0)
    assert elo_depuis_score(0.64) == pytest.approx(100, abs=1)
    assert elo_depuis_score(0.36) == pytest.approx(-100, abs=1)


def test_statistiques():
    s = statistiques([1, 1, 0.5, 0])
    assert (s["victoires"], s["nulles"], s["defaites"]) == (2, 1, 1)
    assert s["score"] == pytest.approx(0.625)
    assert s["elo_min"] < s["elo"] < s["elo_max"]


def test_ouvertures_distinctes():
    ouv = generer_ouvertures("gardner", 49, demi_coups=2)
    assert len(ouv) == 49 and len({tuple(o) for o in ouv}) == 49


def test_mini_tournoi():
    joueurs = ["alphabeta", "aleatoire"]
    res = lancer_tournoi(joueurs, nb_ouvertures=2, budget=300, afficher=False)
    assert len(res) == 4                                  # 2 ouvertures x 2 couleurs
    stats = resumer(joueurs, res)[("alphabeta", "aleatoire")]
    assert stats["parties"] == 4 and stats["score"] >= 0.75
