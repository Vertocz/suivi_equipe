import pandas as pd
import numpy as np

# ----------------------------
# 1) CHARGE PSYCHO-PHYSIO
# ----------------------------

def compute_charge(row):
    """
    Charge brute : fatigue + douleur + stress - sommeil - humeur
    Va de -13 (très bien) à +7 (très mauvais)
    """
    return row["fatigue"] + row["douleur"] + row["stress"] - row["sommeil"] - row["humeur"]

def normalize_charge(charge):
    """
    Convertit la charge [-13 -> +7] en indicateur 0 → 100 :
    - 100 = bien-être maximal
    - 0 = état très dégradé
    """
    min_c, max_c = -13, 7
    norm = (charge - min_c) / (max_c - min_c)
    return 100 * (1 - norm)  # inversé = plus grand → meilleur

# ----------------------------
# 2) VARIABILITÉ / STABILITÉ
# ----------------------------

def compute_variability(df):
    """
    Évalue si les variations quotidiennes sont faibles, normales ou fortes.
    Retourne un texte + un score.
    """
    if len(df) < 5:
        return "Données insuffisantes", None

    df = df.sort_values("date")
    df["variation"] = df["charge_norm"].diff().abs()

    var = df["variation"].rolling(5).mean().iloc[-1]

    if var < 5:
        niveau = "Très stable"
    elif var < 15:
        niveau = "Variations modérées"
    else:
        niveau = "Fluctuations importantes"

    return niveau, float(var)

# ----------------------------
# 3) DIFFICULTÉ ↔ PLAISIR
# ----------------------------

def correlation_difficulte_plaisir(df):
    """
    Corrélation difficulté/plaisir + analyse par sport
    """
    res = {}

    if df.empty:
        return None

    # Corrélation globale
    if df["difficulte"].std() == 0 or df["plaisir"].std() == 0:
        corr = None
    else:
        corr = df["difficulte"].corr(df["plaisir"])

    res["correlation_globale"] = round(corr, 2)

    # Par sport
    correlations = {}
    for sport, group in df.groupby("sport"):
        if len(group) >= 3 and group["difficulte"].std() > 0 and group["plaisir"].std() > 0:
            correlations[sport] = round(group["difficulte"].corr(group["plaisir"]), 2)
        else:
            correlations[sport] = None

    res["correlation_par_sport"] = correlations

    return res
