import streamlit as st
import os
import time
from datetime import date, datetime, timedelta
from supabase_client import supabase
from update_billets_from_storage import update_billets_from_storage
from analyse import compute_charge, normalize_charge, compute_variability, correlation_difficulte_plaisir
import pandas as pd
from streamlit_plotly_events import plotly_events
import plotly.graph_objects as go


# --- Initialisation de la session ---
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.type_user = None

# --- Fonctions utilitaires ---
def afficher_billets(user: dict):
    """
    Affiche tous les billets de train pour la joueuse depuis la table 'billets'.
    Chaque billet est affiché avec un lien cliquable pour téléchargement.
    """
    billets = (
        supabase.table("billets")
        .select("*")
        .eq("joueuse_id", user['id'])
        .order("created_at", desc=True)
        .execute()
        .data
    )

    if not billets:
        st.info("Aucun billet de train disponible pour le moment.")
        return

    st.subheader("Vos billets de train")

    for b in billets:
        st.markdown(f"**Billet : {b['nom_fichier']}**")
        
        url = b.get("url_stockage")
        if not url:
            st.warning("Pas d'URL disponible pour ce billet.")
            continue

        # Lien cliquable / téléchargement
        st.markdown(f"[Ouvrir / Télécharger le billet]({url})", unsafe_allow_html=True)
        st.divider()

def graph_suivi_sportif(joueuse):
    activites = (
        supabase.table("activites")
        .select("*")
        .eq("joueuse_id", joueuse["id"])
        .order("date", desc=False)  # Tri chronologique
        .execute()
        .data
    )

    if not activites:
        st.info("Aucune activité enregistrée.")
    else:
        # --- Filtrer les 30 derniers jours ---
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        activites_30j = [
            a for a in activites
            if pd.to_datetime(a["date"]).date() >= thirty_days_ago
        ]

        if not activites_30j:
            st.info("Aucune activité enregistrée dans les 30 derniers jours.")
        else:
            # --- Préparer le DataFrame ---
            df = pd.DataFrame(activites_30j)
            df["date"] = pd.to_datetime(df["date"]).dt.date

            # --- Calculer les moyennes par jour ---
            df_avg = df.groupby("date").agg({
                "plaisir": "mean",
                "difficulte": "mean"
            }).reset_index()

            # --- Créer le graphique (UNE SEULE FOIS) ---
            fig = go.Figure()

            # --- Ligne moyenne plaisir (axe y1) ---
            fig.add_trace(go.Scatter(
                x=df_avg["date"],
                y=df_avg["plaisir"],
                mode="lines+markers",
                line=dict(color="green", dash="dash"),
                marker=dict(color="green"),
                name="",  # Pas de légende
                yaxis="y1",
                showlegend=False,
                hoverinfo="skip",  # Désactive le survol
            ))

            # --- Ligne moyenne difficulté (axe y2) ---
            fig.add_trace(go.Scatter(
                x=df_avg["date"],
                y=df_avg["difficulte"],
                mode="lines+markers",
                line=dict(color="red", dash="dash"),
                marker=dict(color="red"),
                name="",  # Pas de légende
                yaxis="y2",
                showlegend=False,  
                hoverinfo="skip",  # Désactive le survol
            ))

            # --- Points plaisir (axe y1) ---
            fig.add_trace(go.Scatter(
                x=df["date"],
                y=df["plaisir"],
                mode="markers",
                marker=dict(color="green", size=10),
                name="Plaisir séance",  # Légende pour les points
                customdata=df[["sport", "duree", "commentaire"]],
                hovertemplate=(
                    "<b>%{x|%d/%m}</b><br>"
                    "Plaisir: %{y}<br>"
                    "Sport: %{customdata[0]}<br>"
                    "Durée: %{customdata[1]}<br>"
                    "%{customdata[2]}<extra></extra>"
                ),
                yaxis="y1",
            ))

            # --- Points difficulté (axe y2) ---
            fig.add_trace(go.Scatter(
                x=df["date"],
                y=df["difficulte"],
                mode="markers",
                marker=dict(color="red", size=10),
                name="Difficulté séance",  # Légende pour les points
                customdata=df[["sport", "duree", "commentaire"]],
                hovertemplate=(
                    "<b>%{x|%d/%m}</b><br>"
                    "Difficulté: %{y}<br>"
                    "Sport: %{customdata[0]}<br>"
                    "Durée: %{customdata[1]}<br>"
                    "%{customdata[2]}<extra></extra>"
                ),
                yaxis="y2",
            ))

            # --- Mise en forme du graphique ---
            fig.update_layout(
                xaxis=dict(title="Date"),
                yaxis=dict(title="Plaisir", range=[0, 10], side="left", color="green"),
                yaxis2=dict(title="Difficulté", range=[0, 10], side="right", overlaying="y", color="red"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white",
                hovermode="closest",
                height=500,
                margin=dict(l=40, r=40, t=60, b=20),
            )

            # --- Affichage UNIQUE du graphique ---
            st.plotly_chart(fig, use_container_width=True, key="graphique_suivi")

def verifier_utilisateur(numero: str):
    """Vérifie si le numéro appartient à une joueuse ou un membre du staff."""
    try:
        joueuse = supabase.table("joueuses").select("*").eq("numero_tel", numero).execute().data
        if joueuse:
            return joueuse[0], "joueuse"
        staff = supabase.table("staff").select("*").eq("numero_tel", numero).execute().data
        if staff:
            return staff[0], "staff"
        return None, None
    except Exception as e:
        st.error(f"Erreur lors de la vérification : {e}")
        return None, None

def afficher_page_joueuse(user: dict):
    """Affiche la page dédiée aux joueuses."""
    choix = st.radio("Que voulez-vous faire ?", ["Billets de train", "Suivi sportif"])
    if choix == "Billets de train":
        st.subheader("Billets et Carte Avantage")
        afficher_billets(user)

    if choix == "Suivi sportif":
        st.subheader("Suivi sportif")
        st.write("Renseigne ici ton activité du jour 👇")
        # --- Formulaire de saisie ---
        with st.form("form_activite"):
            sport = st.selectbox(
                    "Sport pratiqué",
                    ["⛹️‍♀️Basket", "🚴‍♂️Vélo", "⚽ Football", "🏃‍♂️Course à pied", "🏓Tennis de table", "🏸Badminton", "🏊‍♂️Natation", "🏋️‍♂️Renforcement musculaire", "Autre"]
                )
            duree = st.text_input("⏱️Durée")
            difficulte = st.slider("Difficulté ressentie (1 = 😁, 10 = 🥵)", 1, 10, 5)
            plaisir = st.slider("Plaisir pris (1 = 😡, 10 = 🥰)", 1, 10, 5)
            date_activite = st.date_input("📅Date de l'activité", date.today(), format="DD/MM/YYYY")
            commentaire = st.text_area("🗣️Commentaires (facultatif)")
            submitted = st.form_submit_button("Enregistrer")

        # --- Traitement du formulaire ---
        if submitted:
            try:
                data = {
                    "joueuse_id": user["id"],
                    "sport": sport,
                    "duree": duree,
                    "difficulte": difficulte,
                    "plaisir": plaisir,
                    "commentaire": commentaire,
                    # Conversion explicite pour éviter le bug de sérialisation
                    "date": date_activite.isoformat(),
                }

                response = supabase.table("activites").insert(data).execute()
                st.success("✅ Activité enregistrée avec succès !")

            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement : {e}")
        graph_suivi_sportif(st.session_state.user)

def afficher_page_staff(user: dict):
    st.title("Espace Staff")

    # ----------------------
    # Charger la table joueuses
    # ----------------------
    data = supabase.table("joueuses").select("*").execute()

    if not data.data:
        st.warning("Aucune joueuse trouvée dans la base de données.")
        return

    joueuses = data.data

    # Liste déroulante des joueuses
    choix_joueuse = st.selectbox(
        "Sélectionnez une joueuse",
        [f"{j['prenom']} {j['nom']}" for j in joueuses],
        index=None,
        placeholder="Choisir une joueuse..."
    )

    if choix_joueuse is None:
        return

    joueuse_selectionnee = next(
        (j for j in joueuses if f"{j['prenom']} {j['nom']}" == choix_joueuse),
        None
    )

    if joueuse_selectionnee is None:
        st.error("Erreur : impossible de retrouver la joueuse sélectionnée.")
        return

    st.markdown(f"## 👤 {choix_joueuse}")

    # ================================
    # 1) GRAPHIQUE DE SUIVI
    # ================================
    st.subheader("📈 Suivi sportif (forme)")
    graph_suivi_sportif(joueuse_selectionnee)


    # =========================================
    # 2) ANALYSE DU SUIVI DE FORME (suivi_forme)
    # =========================================
    st.subheader("🧠 Analyse du bien-être")

    data_forme = (
        supabase.table("suivi_forme")
        .select("*")
        .eq("joueuse_id", joueuse_selectionnee["id"])
        .order("date", desc=False)
        .execute()
        .data
    )

    if data_forme:
        df_forme = pd.DataFrame(data_forme)
        df_forme["date"] = pd.to_datetime(df_forme["date"])

        # Calcul des indicateurs
        df_forme["charge"] = df_forme.apply(compute_charge, axis=1)
        df_forme["charge_norm"] = df_forme["charge"].apply(normalize_charge)

        variabilite_txt, variabilite_score = compute_variability(df_forme)

        # --- Affichage ---
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Charge psycho-physiologique (0-100)",
                f"{df_forme['charge_norm'].iloc[-1]:.0f}"
            )
        with col2:
            st.metric(
                "Variabilité",
                variabilite_txt,
                delta=f"{variabilite_score:.1f}" if variabilite_score else "N/A"
            )

        # Optionnel : afficher le dataframe ou les valeurs brutes
        with st.expander("Voir les données analysées"):
            st.dataframe(df_forme)

    else:
        st.info("Aucun enregistrement de suivi de forme pour cette joueuse.")


    # =======================================================
    # 3) ANALYSE DIFFICULTÉ ↔ PLAISIR (table : activites)
    # =======================================================
    st.subheader("🎭 Relation difficulté ↔ plaisir")

    data_act = (
        supabase.table("activites")
        .select("*")
        .eq("joueuse_id", joueuse_selectionnee["id"])
        .order("date", desc=False)
        .execute()
        .data
    )

    if data_act:
        df_act = pd.DataFrame(data_act)
        df_act["date"] = pd.to_datetime(df_act["date"])

        corr = correlation_difficulte_plaisir(df_act)

        # Corrélation globale
        if corr and corr["correlation_globale"] is not None:
            global_corr = corr["correlation_globale"]
            signe = "🔼 positif" if global_corr > 0 else "🔽 négatif"
            st.markdown(
                f"**Corrélation globale :** `{global_corr:.2f}` ({signe})"
            )
        else:
            st.write("Corrélation globale : non significative")

        # Corrélations par sport
        st.markdown("### Par sport")
        for sport, c in corr["correlation_par_sport"].items():
            if c is None:
                st.write(f"- **{sport}** : pas assez de données")
            else:
                signe = "🔼" if c > 0 else "🔽"
                st.write(f"- **{sport}** : `{c:.2f}` {signe}")

        with st.expander("Voir les activités brutes"):
            st.dataframe(df_act)

    else:
        st.info("Aucune activité enregistrée pour cette joueuse.")

# --- Page d'accueil ---
st.title("Pôle France Para Basketball Adapté")

# --- Zone de connexion ---
numero = st.text_input("📱Entrez votre numéro de téléphone", placeholder="Ex: 0612345678")
if st.button("🚪Accéder"):
    if len(numero) != 10 or not numero.startswith(("06", "07")):
        st.error("Numéro de téléphone invalide. Veuillez entrer un numéro français valide (10 chiffres, commence par 06 ou 07).")
    else:
        with st.spinner("Vérification en cours..."):
            user, type_user = verifier_utilisateur(numero)
            if user:
                st.session_state.user = user
                st.session_state.type_user = type_user
                st.rerun()  # Utilisation de st.rerun() au lieu de st.experimental_rerun()
            else:
                st.error("Numéro inconnu.")

# --- Après identification ---
if st.session_state.user:
    st.success(f"Bienvenue {st.session_state.user['prenom']} !")

    if st.session_state.type_user == "joueuse":
        afficher_page_joueuse(st.session_state.user)
    else:
        afficher_page_staff(st.session_state.user)
