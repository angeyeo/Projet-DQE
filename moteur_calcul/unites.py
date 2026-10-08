"""
Conversions d'unités du moteur : source UNIQUE.

Convention interne du moteur (toutes les fonctions publiques) :
    longueurs          m        (sections et enrobages : cm, suffixe _cm)
    surfaces           m²       (sections d'acier : cm², suffixe _cm2)
    forces             kN
    charges linéaires  kN/m
    charges surfaciques et contraintes de sol   kN/m²
    résistances des matériaux                   MPa  (fc28, fe)
    moments            kN·m

Chaque conversion est une fonction nommée : aucun facteur « magique »
(0.1, 1000, 1e4...) ne doit apparaître dans les formules. Les facteurs
sont exacts (définitions SI), pas des approximations.
"""

# Facteurs exacts (définitions SI)
KN_PAR_MN = 1000.0
CM_PAR_M = 100.0
CM2_PAR_M2 = 10_000.0
KN_M2_PAR_MPA = 1000.0      # 1 MPa = 1 MN/m² = 1000 kN/m²
KN_M2_PAR_BAR = 100.0       # 1 bar = 100 kPa = 100 kN/m²
KN_CM2_PAR_MPA = 0.1        # 1 MPa = 1 N/mm² = 0,1 kN/cm²


def _nombre(valeur, nom):
    if valeur is None:
        raise ValueError(f"Conversion impossible : {nom} non renseigné(e).")
    try:
        v = float(valeur)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Conversion impossible : {nom} n'est pas un nombre ({valeur!r}).") from exc
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError(f"Conversion impossible : {nom} n'est pas un nombre fini.")
    return v


# --- Longueurs / surfaces -------------------------------------------------
def cm_vers_m(v):
    return _nombre(v, "longueur (cm)") / CM_PAR_M


def m_vers_cm(v):
    return _nombre(v, "longueur (m)") * CM_PAR_M


def cm2_vers_m2(v):
    return _nombre(v, "surface (cm²)") / CM2_PAR_M2


def m2_vers_cm2(v):
    return _nombre(v, "surface (m²)") * CM2_PAR_M2


# --- Forces / moments -----------------------------------------------------
def kn_vers_mn(v):
    return _nombre(v, "force (kN)") / KN_PAR_MN


def mn_vers_kn(v):
    return _nombre(v, "force (MN)") * KN_PAR_MN


# --- Contraintes ----------------------------------------------------------
def mpa_vers_kn_m2(v):
    return _nombre(v, "contrainte (MPa)") * KN_M2_PAR_MPA


def kn_m2_vers_mpa(v):
    return _nombre(v, "contrainte (kN/m²)") / KN_M2_PAR_MPA


def bar_vers_kn_m2(v):
    return _nombre(v, "contrainte (bar)") * KN_M2_PAR_BAR


def mpa_vers_kn_cm2(v):
    return _nombre(v, "contrainte (MPa)") * KN_CM2_PAR_MPA


UNITES_CONTRAINTE_SOL = {
    "kN/m²": lambda v: _nombre(v, "contrainte (kN/m²)"),
    "kPa": lambda v: _nombre(v, "contrainte (kPa)"),  # 1 kPa = 1 kN/m²
    "MPa": mpa_vers_kn_m2,
    "bar": bar_vers_kn_m2,
}


def contrainte_sol_en_kn_m2(valeur, unite):
    """Convertit une contrainte de sol exprimée dans `unite` vers kN/m²
    (unité interne). Unité inconnue -> erreur, jamais de supposition."""
    try:
        conv = UNITES_CONTRAINTE_SOL[unite]
    except KeyError:
        raise ValueError(
            f"Unité de contrainte de sol inconnue : {unite!r} "
            f"(attendu : {', '.join(UNITES_CONTRAINTE_SOL)})."
        ) from None
    return conv(valeur)


def arrondi_superieur(valeur, pas):
    """Arrondi constructif au multiple supérieur de `pas` (ex. 5 cm).
    Tolérance numérique : 117.0000000001 reste 120 mais 115.0 reste 115."""
    import math

    v = _nombre(valeur, "valeur à arrondir")
    if pas <= 0:
        raise ValueError("Le pas d'arrondi doit être positif.")
    return math.ceil(round(v / pas, 9)) * pas
