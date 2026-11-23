# MCTS contre alpha-bêta aux (mini-)échecs — INF8790

**Question de recherche :** MCTS (UCT) joue mal aux échecs parce que ses simulations
aléatoires ne voient pas les **pièges peu profonds**. Quelles modifications comblent
l'écart avec alpha-bêta, **à budget de calcul égal** ?

## Installation

```bash
pip install -r requirements.txt
python -m pytest -q          # 44 tests, ~15 s
```

## Les méthodes comparées

| Nom | Spécification | Idée |
|---|---|---|
| **B1** | `alphabeta` | Alpha-bêta, approfondissement itératif, quiescence, MVV-LVA, table de transposition |
| **B2** | `uct` | UCT pur : simulations aléatoires jusqu'à la fin de la partie |
| **M1** | `uct:politique=captures,eps=0.8` | Simulations guidées : 80 % du temps, la meilleure capture (MVV-LVA) |
| **M2** | `uct:coupure=4` | Simulation coupée après 4 coups, puis évaluation matérielle → probabilité |
| **M3** | `uct:solver=1` | MCTS-Solver : victoires/défaites prouvées remontées dans l'arbre |
| **M4** | `uct:minimax=1` | Hybride : feuilles évaluées par un mini alpha-bêta (prof. 1 + quiescence) |
| **M5** | `uct:biais=1.0` | Biais progressif : bonus heuristique qui s'efface avec les visites |
| **M1+M2+M3** | combinaison | La configuration « tout compris » |

Tous les noms ci-dessus s'utilisent directement en ligne de commande (`--joueurs B1 M2`),
et toutes les options se combinent : `"uct:c=1.0,politique=captures,coupure=2,solver=1,biais=0.5"`.

## Lancer les expériences du rapport

```bash
# Vérification rapide que tout fonctionne (~10 min)
python -m minichess.experiences --etape tout --rapide

# Campagne complète (plusieurs heures : à lancer la nuit, idéalement avec tous les cœurs)
python -m minichess.experiences --etape tout --processus 8
#   + problèmes Lichess si téléchargés :
python -m minichess.experiences --etape puzzles --puzzles lichess_db_puzzle.csv.zst

# Refaire seulement les figures
python -m minichess.experiences --etape graphiques
```

Chaque étape écrit ses CSV et figures dans `resultats/` :

| Étape | Ce qu'elle mesure | Fichiers |
|---|---|---|
| `principal` | Elo de chaque méthode contre B1 (budget 10 000, 60 parties chacune) | `principal.csv`, `fig_principal.png` |
| `budgets` | Évolution de l'écart avec le budget (2 000 → 20 000) | `budgets.csv`, `fig_budgets.png` |
| `ablation` | Effet de C, de la coupure d, de ε ; ablation d'alpha-bêta | `ablation.csv`, `fig_ablation.png` |
| `pieges` | **Taux de gaffes** sur des positions-pièges, par niveau de piège | `pieges.csv`, `fig_pieges.png` |
| `puzzles` | Taux de réussite sur les problèmes Lichess (échecs complets) | `puzzles.csv`, `fig_puzzles.png` |

Les CSV `*_parties.csv` gardent chaque partie (coups, durée, ouverture) pour d'autres analyses.

## Commandes à la pièce

```bash
# Tournoi : chaque joueur contre B1 (ou toutes rondes sans --contre)
python -m minichess.tournoi --joueurs B2 M1 M2 --contre B1 --ouvertures 30 --budget 10000 --processus 4

# Positions-pièges : générer la banque puis tester
python -m minichess.pieges --generer 200 --fichier donnees/pieges.json --processus 4
python -m minichess.pieges --fichier donnees/pieges.json --joueurs B1 B2 M1 M2 --budget 5000

# Problèmes Lichess (database.lichess.org)
python -m minichess.puzzles --fichier lichess_db_puzzle.csv.zst --themes mateIn1 mateIn2 hangingPiece \
    --elo-max 1600 --n 300 --joueurs B1 B2 M2 --budget 20000 --processus 4
```

## Structure

```
minichess/
  jeu.py            Interface commune Jeu (contrat entre les deux parties)
  gardner.py        Mini-échecs de Gardner 5×5                          [A]
  echecs.py         Échecs complets via python-chess (même interface)   [A]
  evaluation.py     Évaluation matérielle, proba_victoire(), MVV-LVA     [A, partagé]
  joueurs/
    base.py         Classe Joueur + JoueurAleatoire
    alphabeta.py    B1                                                  [A]
    mcts.py         B2, M1 à M5 (un seul JoueurUCT paramétrable)         [B]
    __init__.py     Registre + préréglages B1, B2, M1..M5
  arene.py          jouer_partie(), ouvertures aléatoires               [A]
  tournoi.py        Tournois + Elo et IC à 95 %                         [A]
  puzzles.py        Problèmes Lichess                                   [A]
  pieges.py         Banque de positions-pièges, taux de gaffes          [B]
  experiences.py    Toute la campagne + figures                         [A + B]
tests/              44 tests (règles vs python-chess, alpha-bêta, MCTS, tournoi)
donnees/            4 problèmes d'exemple au format Lichess
```

## Choix méthodologiques (à reprendre dans le rapport)

- **Budget = appels à `jouer()`**, simulations comprises (`coups_legaux()` est gratuit).
  Les méthodes sont comparées à quantité de calcul égale, quelle que soit la vitesse du code.
  Une itération MCTS interrompue par le budget n'est pas rétropropagée.
- **Même évaluation partout** (`evaluation.py`) : la différence vient de la recherche, pas de l'heuristique.
- **Ouvertures** : 3 demi-coups aléatoires, chaque ouverture jouée deux fois en inversant les couleurs.
- **Elo** : calculé à partir du score moyen ; intervalle de confiance à 95 % par approximation normale.
- **Pièges** (`pieges.py`) : un coup est un piège s'il perd ≥ 3 pions par rapport au meilleur coup,
  selon un alpha-bêta de profondeur 4 + quiescence. Niveau 1 = réfutation visible avec une seule
  réponse adverse ; niveau 2 = il en faut deux. *Limite* : la référence est elle-même un alpha-bêta,
  ce qui avantage B1 sur ce test ; le dire dans la discussion.
- **MCTS** : récompenses dans [0, 1] ; coup final = enfant le plus visité (avec le Solver : un coup
  prouvé gagnant est joué, un coup prouvé perdant est évité).

## Chiffres de référence

| Mesure | Valeur |
|---|---|
| Perft Gardner, profondeurs 1 à 5 | 7 · 53 · 506 · 4 775 · 52 512 (1 à 4 vérifiés contre python-chess) |
| Vitesse (Python) | ≈ 30 000 positions/s |
| Profondeur d'alpha-bêta (position initiale) | budget 1 000 → 4 · 10 000 → 6 · 50 000 → 7 |
| Itérations MCTS, budget 5 000 (position initiale) | B2 ≈ 60 · M2 ≈ 1 000 |

## Règles du 5×5 implémentées

Échecs standards sans roque, sans double pas et sans prise en passant ; promotion au choix.
Fin : mat, pat, triple répétition, matériel insuffisant, 50 demi-coups sans capture ni coup de pion,
ou 200 demi-coups au total (voir `JeuGardner.LIMITE_*`).

## Références

- Kocsis & Szepesvári (2006). *Bandit based Monte-Carlo planning.* ECML.
- Browne et al. (2012). *A survey of Monte Carlo tree search methods.* IEEE TCIAIG.
- Chaslot et al. (2008). *Progressive strategies for Monte-Carlo tree search.* New Math. and Nat. Computation.
- Winands, Björnsson & Saito (2008). *Monte-Carlo tree search solver.* Computers and Games.
- Ramanujan, Sabharwal & Selman (2010). *On adversarial search spaces and sampling-based planning.* ICAPS.
- Baier & Winands (2018). *MCTS-minimax hybrids with state evaluations.* JAIR.
- Mhalla & Prost (2013). *Gardner's minichess variant is solved.* ICGA Journal.
- Silver et al. (2018). *A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play.* Science.
