import streamlit as st
import os
import time
from datetime import date, datetime, timedelta
from supabase_client import supabase
from update_billets_from_storage import update_billets_from_storage
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
                    ["⛹️‍♀️Basket", "🚴‍♂️Vélo", "🏃‍♂️Course à pied", "🏓Tennis de table", "🏸Badminton", "🏊‍♂️Natation", "🏋️‍♂️Renforcement musculaire", "Autre"]
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
    """Affiche la page dédiée au staff."""
    if user["numero_tel"] == os.getenv("MON_NUMERO"):
        if st.button("Mettre à jour les billets"):
            placeholder = st.empty()
            placeholder.info("Mise à jour en cours…")
            update_billets_from_storage()
            placeholder.success("Mise à jour terminée !")
            time.sleep(3)
            placeholder.empty()

    choix = st.radio("Que voulez-vous faire ?", ["Voir mes billets de train", "Consulter les suivis sportifs"])
    if choix == "Voir mes billets de train":
        afficher_billets(user)
    elif choix == "Consulter les suivis sportifs":
        st.subheader("Suivi des joueuses")
        st.write("📊 Sélectionnez une joueuse pour consulter son suivi sportif.")

        # --- Récupération des joueuses en fonction du staff ---
        try:
            query = supabase.table("joueuses").select("id, prenom, nom, categorie")

            # Cas 1 → staff masculin uniquement
            if user.get("masculin") and not user.get("feminin"):
                query = query.eq("categorie", "masculin")

            # Cas 2 → staff féminin uniquement
            elif user.get("feminin") and not user.get("masculin"):
                query = query.eq("categorie", "feminin")

            # Cas 3 → staff sur les deux → pas de filtre

            joueuses = query.order("prenom", desc=False).execute().data

        except Exception as e:
            st.error(f"Erreur lors du chargement des joueuses/joueurs : {e}")
            return

        if not joueuses:
            st.warning("Aucune joueuse trouvée dans la base de données.")
            return

        # --- Liste déroulante des joueuses ---
        noms_joueuses = [f"{j['prenom']} {j['nom']}" for j in joueuses]
        choix_joueuse = st.selectbox("Choisissez une joueuse :", options=noms_joueuses)

        # --- Trouver la joueuse sélectionnée ---
        joueuse_selectionnee = next((j for j in joueuses if f"{j['prenom']} {j['nom']}" == choix_joueuse), None)

        if joueuse_selectionnee:
            st.markdown(f"### 📈 Suivi de {choix_joueuse}")
            graph_suivi_sportif(joueuse_selectionnee)

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
