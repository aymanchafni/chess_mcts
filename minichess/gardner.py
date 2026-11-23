"""Mini-échecs de Gardner (5×5).

Position initiale :
    5  r n b q k
    4  p p p p p
    3  . . . . .
    2  P P P P P
    1  R N B Q K
       a b c d e

Règles : celles des échecs, sauf pas de roque, pas de double pas des pions
(donc pas de prise en passant). Un pion qui atteint la dernière rangée est promu
(dame, tour, fou ou cavalier).

Fin de partie :
- mat : perte du joueur au trait ;
- pat, triple répétition, matériel insuffisant : nulle ;
- LIMITE_SANS_PROGRES demi-coups sans capture ni coup de pion : nulle ;
- LIMITE_DEMI_COUPS demi-coups au total : nulle (garde-fou pour les tournois).

Représentation : un tuple de 25 entiers, case = rangée * 5 + colonne
(rangée 0 = rangée « 1 » des blancs, colonne 0 = colonne « a »).
Pièce positive = blanche, négative = noire, 0 = vide.
Un coup est un tuple (depart, arrivee, promotion) avec promotion = 0 ou un type de pièce.
"""

from .jeu import Jeu

VIDE, PION, CAVALIER, FOU, TOUR, DAME, ROI = range(7)
VALEURS = (0, 100, 300, 300, 500, 900, 0)
LETTRES = ".pnbrqk"
PROMOTIONS = (DAME, TOUR, FOU, CAVALIER)
N = 5


def _sur_plateau(r, c):
    return 0 <= r < N and 0 <= c < N


def _precalculer():
    sauts, voisins, rayons = [], [], []
    dirs_cav = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
    dirs_roi = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    for case in range(N * N):
        r, c = divmod(case, N)
        sauts.append(tuple((r + dr) * N + c + dc for dr, dc in dirs_cav if _sur_plateau(r + dr, c + dc)))
        voisins.append(tuple((r + dr) * N + c + dc for dr, dc in dirs_roi if _sur_plateau(r + dr, c + dc)))
        rays = []
        for dr, dc in dirs_roi:  # 4 premières = lignes (tour), 4 dernières = diagonales (fou)
            ray, rr, cc = [], r + dr, c + dc
            while _sur_plateau(rr, cc):
                ray.append(rr * N + cc)
                rr, cc = rr + dr, cc + dc
            rays.append(tuple(ray))
        rayons.append(tuple(rays))
    return tuple(sauts), tuple(voisins), tuple(rayons)


SAUTS, VOISINS, RAYONS = _precalculer()
LIGNES = slice(0, 4)
DIAGONALES = slice(4, 8)


def case_attaquee(plateau, case, par):
    """Vrai si `case` est attaquée par le camp `par` (+1 blancs / -1 noirs)."""
    r, c = divmod(case, N)
    # Pions : un pion blanc en (r-1, c±1) attaque (r, c) ; un pion noir en (r+1, c±1).
    rp = r - par
    if 0 <= rp < N:
        for cp in (c - 1, c + 1):
            if 0 <= cp < N and plateau[rp * N + cp] == par * PION:
                return True
    for a in SAUTS[case]:
        if plateau[a] == par * CAVALIER:
            return True
    for a in VOISINS[case]:
        if plateau[a] == par * ROI:
            return True
    rays = RAYONS[case]
    for ray in rays[LIGNES]:
        for a in ray:
            p = plateau[a]
            if p:
                if p == par * TOUR or p == par * DAME:
                    return True
                break
    for ray in rays[DIAGONALES]:
        for a in ray:
            p = plateau[a]
            if p:
                if p == par * FOU or p == par * DAME:
                    return True
                break
    return False


def coups_pseudo_legaux(plateau, trait):
    """Coups qui respectent le déplacement des pièces, sans vérifier l'échec au roi."""
    coups = []
    for de in range(N * N):
        p = plateau[de] * trait
        if p <= 0:
            continue
        if p == PION:
            r, c = divmod(de, N)
            r2 = r + trait
            if not 0 <= r2 < N:
                continue
            promo = r2 == (N - 1 if trait == 1 else 0)
            cibles = []
            a = r2 * N + c
            if plateau[a] == 0:
                cibles.append(a)
            for c2 in (c - 1, c + 1):
                if 0 <= c2 < N:
                    a = r2 * N + c2
                    if plateau[a] * trait < 0:
                        cibles.append(a)
            for a in cibles:
                if promo:
                    coups.extend((de, a, pr) for pr in PROMOTIONS)
                else:
                    coups.append((de, a, 0))
        elif p == CAVALIER or p == ROI:
            for a in (SAUTS if p == CAVALIER else VOISINS)[de]:
                if plateau[a] * trait <= 0:
                    coups.append((de, a, 0))
        else:
            rays = RAYONS[de]
            groupes = rays[LIGNES] if p == TOUR else rays[DIAGONALES] if p == FOU else rays
            for ray in groupes:
                for a in ray:
                    q = plateau[a]
                    if q == 0:
                        coups.append((de, a, 0))
                    else:
                        if q * trait < 0:
                            coups.append((de, a, 0))
                        break
    return coups


def appliquer(plateau, coup):
    de, a, promo = coup
    nouveau = list(plateau)
    piece = nouveau[de]
    nouveau[a] = promo * (1 if piece > 0 else -1) if promo else piece
    nouveau[de] = 0
    return tuple(nouveau)


def position_initiale():
    return (
        TOUR, CAVALIER, FOU, DAME, ROI,
        PION, PION, PION, PION, PION,
        0, 0, 0, 0, 0,
        -PION, -PION, -PION, -PION, -PION,
        -TOUR, -CAVALIER, -FOU, -DAME, -ROI,
    )


class JeuGardner(Jeu):
    LIMITE_SANS_PROGRES = 50   # demi-coups sans capture ni coup de pion
    LIMITE_DEMI_COUPS = 200    # garde-fou absolu

    __slots__ = ("plateau", "_trait", "demi_coups", "sans_progres", "parent", "_coups", "_fini", "_resultat")

    def __init__(self, plateau=None, trait=1, demi_coups=0, sans_progres=0, parent=None):
        self.plateau = plateau if plateau is not None else position_initiale()
        self._trait = trait
        self.demi_coups = demi_coups
        self.sans_progres = sans_progres
        self.parent = parent      # état précédent (pour détecter les répétitions)
        self._coups = None        # cache des coups légaux
        self._fini = None
        self._resultat = 0

    # ---------- interface Jeu ----------
    @property
    def trait(self):
        return self._trait

    def coups_legaux(self):
        if self._coups is None:
            legaux = []
            t = self._trait
            for coup in coups_pseudo_legaux(self.plateau, t):
                apres = appliquer(self.plateau, coup)
                if not case_attaquee(apres, apres.index(t * ROI), -t):
                    legaux.append(coup)
            self._coups = legaux
        return self._coups

    def jouer(self, coup):
        Jeu.compteur += 1
        de, a, _ = coup
        progres = self.plateau[a] != 0 or abs(self.plateau[de]) == PION
        return JeuGardner(
            appliquer(self.plateau, coup),
            -self._trait,
            self.demi_coups + 1,
            0 if progres else self.sans_progres + 1,
            self,
        )

    def est_fini(self):
        if self._fini is None:
            self._fini, self._resultat = self._evaluer_fin()
        return self._fini

    def resultat(self):
        self.est_fini()
        return self._resultat

    def materiel(self):
        total = 0
        for p in self.plateau:
            if p:
                total += VALEURS[p] if p > 0 else -VALEURS[-p]
        return total

    def info_capture(self, coup):
        victime = self.plateau[coup[1]]
        if victime == 0:
            return None
        return VALEURS[abs(victime)], VALEURS[abs(self.plateau[coup[0]])]

    def est_promotion(self, coup):
        return coup[2] != 0

    def en_echec(self):
        t = self._trait
        return case_attaquee(self.plateau, self.plateau.index(t * ROI), -t)

    def cle(self):
        return (self.plateau, self._trait)

    def coup_vers_texte(self, coup):
        de, a, promo = coup
        nom = lambda c: "abcde"[c % N] + str(c // N + 1)
        return nom(de) + nom(a) + (LETTRES[promo] if promo else "")

    def texte_vers_coup(self, texte):
        case = lambda s: (int(s[1]) - 1) * N + "abcde".index(s[0])
        promo = LETTRES.index(texte[4]) if len(texte) > 4 else 0
        return (case(texte[0:2]), case(texte[2:4]), promo)

    # ---------- utilitaires ----------
    def _evaluer_fin(self):
        if not self.coups_legaux():
            return True, (-self._trait if self.en_echec() else 0)
        if self.sans_progres >= self.LIMITE_SANS_PROGRES or self.demi_coups >= self.LIMITE_DEMI_COUPS:
            return True, 0
        if self._materiel_insuffisant() or self._triple_repetition():
            return True, 0
        return False, 0

    def _materiel_insuffisant(self):
        mineurs = 0
        for p in self.plateau:
            t = abs(p)
            if t in (PION, TOUR, DAME):
                return False
            if t in (CAVALIER, FOU):
                mineurs += 1
        return mineurs <= 1

    def _triple_repetition(self):
        # On ne remonte que jusqu'au dernier coup irréversible (capture ou pion).
        vues, etat, pas = 1, self.parent, 1
        while etat is not None and pas <= self.sans_progres:
            if pas % 2 == 0 and etat.plateau == self.plateau:
                vues += 1
                if vues >= 3:
                    return True
            etat, pas = etat.parent, pas + 1
        return False

    @classmethod
    def depuis_texte(cls, lignes, trait=1):
        """Construit une position à partir de 5 chaînes, rangée 5 en premier.
        Ex. ["....k", ".....", ".....", ".....", "K...."]  (majuscules = blancs)."""
        plateau = [0] * (N * N)
        for i, ligne in enumerate(lignes):
            r = N - 1 - i
            for c, ch in enumerate(ligne):
                if ch != ".":
                    t = LETTRES.index(ch.lower())
                    plateau[r * N + c] = t if ch.isupper() else -t
        return cls(tuple(plateau), trait)

    def __str__(self):
        lignes = []
        for r in range(N - 1, -1, -1):
            cases = []
            for c in range(N):
                p = self.plateau[r * N + c]
                ch = LETTRES[abs(p)]
                cases.append(ch.upper() if p > 0 else ch)
            lignes.append(f"{r + 1}  " + " ".join(cases))
        lignes.append("   a b c d e")
        lignes.append("Trait : " + ("blancs" if self._trait == 1 else "noirs"))
        return "\n".join(lignes)
