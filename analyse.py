import pandas as pd
import numpy as np


def compute_charge(row):
    """
    Calcule la charge psycho-physiologique à partir des données de suivi de forme.
    
    Args:
        row: Une ligne du DataFrame contenant fatigue, sommeil, douleur, stress, humeur
    
    Returns:
        float: Score de charge (plus c'est bas, plus l'état est dégradé)
    """
    # Inverser les valeurs négatives (fatigue, douleur, stress)
    # Plus ces valeurs sont élevées, plus c'est négatif
    fatigue_inverse = 6 - row.get('fatigue', 3)
    douleur_inverse = 6 - row.get('douleur', 3)
    stress_inverse = 6 - row.get('stress', 3)
    
    # Sommeil et humeur sont déjà positifs (plus haut = mieux)
    sommeil = row.get('sommeil', 3)
    humeur = row.get('humeur', 3)
    
    # Moyenne des 5 indicateurs
    charge = (fatigue_inverse + sommeil + douleur_inverse + stress_inverse + humeur) / 5
    
    return charge


def normalize_charge(charge):
    """
    Normalise la charge sur une échelle de 0 à 100.
    
    Args:
        charge: Score de charge (entre 1 et 5)
    
    Returns:
        float: Score normalisé entre 0 et 100
    """
    # Convertir l'échelle 1-5 en 0-100
    return ((charge - 1) / 4) * 100


def compute_variability(df_suivi):
    """
    Calcule la variabilité de la charge psycho-physiologique.
    
    Args:
        df_suivi: DataFrame avec la colonne 'charge_norm'
    
    Returns:
        tuple: (niveau_variabilité, score_variabilité)
    """
    if df_suivi.empty or 'charge_norm' not in df_suivi.columns:
        return "Données insuffisantes", None
    
    if len(df_suivi) < 2:
        return "Données insuffisantes", None
    
    # Calcul de l'écart-type
    std_dev = df_suivi['charge_norm'].std()
    
    # Classification de la variabilité
    if std_dev < 10:
        niveau = "Faible"
    elif std_dev < 20:
        niveau = "Modérée"
    else:
        niveau = "Élevée"
    
    return niveau, std_dev


def correlation_difficulte_plaisir(df_activites):
    """
    Calcule la corrélation entre difficulté et plaisir.
    
    Args:
        df_activites: DataFrame contenant au minimum les colonnes 'difficulte', 'plaisir' et 'sport'
    
    Returns:
        dict: Dictionnaire contenant la corrélation globale et par sport
    """
    res = {
        "correlation_globale": None,
        "correlation_par_sport": {}
    }
    
    # Vérifier que le DataFrame n'est pas vide et contient les colonnes nécessaires
    if df_activites.empty:
        return res
    
    if 'difficulte' not in df_activites.columns or 'plaisir' not in df_activites.columns:
        return res
    
    # Calculer la corrélation globale
    try:
        # Vérifier qu'il y a au moins 2 valeurs
        if len(df_activites) < 2:
            res["correlation_globale"] = "Données insuffisantes"
        else:
            corr = df_activites['difficulte'].corr(df_activites['plaisir'])
            
            # Vérifier que la corrélation est un nombre valide
            if pd.notna(corr) and not np.isnan(corr) and not np.isinf(corr):
                res["correlation_globale"] = round(float(corr), 2)
            else:
                res["correlation_globale"] = "Données insuffisantes"
    except Exception as e:
        res["correlation_globale"] = "Erreur de calcul"
    
    # Calculer la corrélation par sport
    if 'sport' in df_activites.columns:
        for sport in df_activites['sport'].unique():
            if pd.isna(sport):
                continue
                
            df_sport = df_activites[df_activites['sport'] == sport]
            
            # Vérifier qu'il y a au moins 2 valeurs pour calculer une corrélation
            if len(df_sport) < 2:
                res["correlation_par_sport"][sport] = "Données insuffisantes"
                continue
            
            try:
                corr_sport = df_sport['difficulte'].corr(df_sport['plaisir'])
                
                if pd.notna(corr_sport) and not np.isnan(corr_sport) and not np.isinf(corr_sport):
                    res["correlation_par_sport"][sport] = round(float(corr_sport), 2)
                else:
                    res["correlation_par_sport"][sport] = "Données insuffisantes"
            except Exception as e:
                res["correlation_par_sport"][sport] = "Erreur de calcul"
    
    return res
