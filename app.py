import streamlit as st
import os
import re
import time
from datetime import date, datetime, timedelta
from supabase_client import supabase
from update_billets_from_storage import update_billets_from_storage
from analyse import compute_charge, normalize_charge, compute_variability, correlation_difficulte_plaisir
import pandas as pd
from streamlit_plotly_events import plotly_events
import plotly.graph_objects as go

st.set_page_config(
    page_title="Pôle France Parabasket Adapté",
    page_icon="🏀",
)

# --- Initialisation de la session ---
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.type_user = None


# --- Fonctions utilitaires ---
def afficher_billets(user: dict):
    """Affiche tous les billets de train pour la joueuse depuis la table 'billets'.
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

        url = "https://fxvotvtapcwzvjhfreqv.supabase.co/storage/v1/object/public/Billets/"+b.get("url_stockage")
        if not url:
            st.warning("Pas d'URL disponible pour ce billet.")
            continue

        st.markdown(f"[Ouvrir / Télécharger le billet]({url})", unsafe_allow_html=True)
        st.divider()


def graph_suivi_sportif(joueuse):
    activites = (
        supabase.table("activites")
        .select("*")
        .eq("joueuse_id", joueuse["id"])
        .order("date", desc=False)
        .execute()
        .data
    )

    if not activites:
        st.info("Aucune activité enregistrée.")
        return

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    activites_30j = [
        a for a in activites
        if pd.to_datetime(a["date"]).date() >= thirty_days_ago
    ]

    if not activites_30j:
        st.info("Aucune activité enregistrée dans les 30 derniers jours.")
        return

    df = pd.DataFrame(activites_30j)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    df_avg = df.groupby("date").agg({
        "plaisir": "mean",
        "difficulte": "mean"
    }).reset_index()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_avg["date"], y=df_avg["plaisir"],
        mode="lines",
        line=dict(color="green", dash="dash"),
        marker=dict(color="green"),
        name="",
        yaxis="y1",
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df_avg["date"], y=df_avg["difficulte"],
        mode="lines",
        line=dict(color="red", dash="dash"),
        marker=dict(color="red"),
        name="",
        yaxis="y2",
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["plaisir"],
        mode="markers",
        marker=dict(color="green", size=10),
        name="Plaisir séance",
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

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["difficulte"],
        mode="markers",
        marker=dict(color="red", size=10),
        name="Difficulté séance",
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

    fig.update_layout(
        xaxis=dict(title="Date"),
        yaxis=dict(title="Plaisir", range=[0, 10], side="left", color="green"),
        yaxis2=dict(title="Difficulté", range=[0, 10], side="right",
                    overlaying="y", color="red"),
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
        template="plotly_white",
        hovermode="closest",
        height=500,
        margin=dict(l=40, r=40, t=60, b=20),
    )

    st.plotly_chart(fig, use_container_width=True, key="graphique_suivi")

    st.subheader("📋 Historique des séances")

    df_sorted = df.sort_values("date", ascending=False)

    for _, row in df_sorted.iterrows():
        st.markdown(f"""
**🗓️ {row['date'].strftime('%d/%m/%Y')} — {row['sport']}**
- ⏱️ Durée : {row['duree']}
- 💪 Difficulté : {row['difficulte']}/10
- 😄 Plaisir : {row['plaisir']}/10
- 🗣️ Commentaire : {row['commentaire'] or '_Aucun_'}
""")

        if st.button("🗑️ Supprimer ce suivi", key=f"suppr_{row['id']}"):
            st.warning("Es-tu sûr de vouloir supprimer cette activité ?", icon="⚠️")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Oui, supprimer", key=f"conf_suppr_{row['id']}"):
                    try:
                        supabase.table("activites").delete().eq("id", row["id"]).execute()
                        st.info(str(row["id"])+" a été supprimé.")
                        st.success("✅ Activité supprimée.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de la suppression : {e}")

            with col2:
                if st.button("❌ Non, annuler", key=f"cancel_suppr_{row['id']}"):
                    st.info("Suppression annulée.")

            st.divider()


def graph_suivi_forme(joueuse):
    try:
        data = (
            supabase.table("suivi_forme")
            .select("*")
            .eq("joueuse_id", joueuse["id"])
            .order("date", desc=False)
            .execute()
            .data
        )
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")
        return

    if not data:
        st.info("Aucune donnée enregistrée.")
        return

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    data_30j = [
        a for a in data
        if pd.to_datetime(a["date"]).date() >= thirty_days_ago
    ]

    if not data_30j:
        st.info("Aucune donnée enregistrée dans les 30 derniers jours.")
        return

    df = pd.DataFrame(data_30j)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    df_avg = df.groupby("date").agg({
        "fatigue": "mean",
        "sommeil": "mean",
        "douleur": "mean",
        "stress": "mean",
        "humeur": "mean",
    }).reset_index()

    fig = go.Figure()

    infos = {
        "fatigue": "Fatigue",
        "sommeil": "Sommeil",
        "douleur": "Douleur",
        "stress": "Stress",
        "humeur": "Humeur",
    }

    for key, label in infos.items():
        fig.add_trace(go.Scatter(
            x=df_avg["date"], y=df_avg[key],
            mode="lines+markers",
            line=dict(dash="dash"),
            name=f"{label}",
            hoverinfo="skip"
        ))

    fig.update_layout(
        xaxis=dict(title="Date"),
        yaxis=dict(title="Score (1–5)", range=[0, 5.5]),
        template="plotly_white",
        hovermode="closest",
        height=500,
        margin=dict(l=40, r=40, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Historique du suivi de forme")

    df_sorted = df.sort_values("date", ascending=False)

    for _, row in df_sorted.iterrows():
        st.markdown(f"""
**🗓️ {row['date'].strftime('%d/%m/%Y')}**
- 🛌 Qualité du sommeil : {row.get('sommeil', '–')}/5
- 😴 Fatigue générale : {row.get('fatigue', '–')}/5
- 🤕 Douleurs : {row.get('douleur', '–')}/5
- 😰 Niveau de stress : {row.get('stress', '–')}/5
- 🙂 Humeur générale : {row.get('humeur', '–')}/5
- 🗣️ Commentaire : {row.get('commentaire', '_Aucun_')}
""")

        if st.button("🗑️ Supprimer ce suivi", key=f"suppr_{row['id']}"):
            st.warning("Es-tu sûr de vouloir supprimer cette activité ?", icon="⚠️")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Oui, supprimer", key=f"conf_suppr_{row['id']}"):
                    try:
                        supabase.table("suivi_forme").delete().eq("id", row["id"]).execute()
                        st.info(str(row["id"])+" a été supprimé.")
                        st.success("✅ Activité supprimée.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de la suppression : {e}")

            with col2:
                if st.button("❌ Non, annuler", key=f"cancel_suppr_{row['id']}"):
                    st.info("Suppression annulée.")

            st.divider()


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
    choix = st.radio("Que voulez-vous faire ?", [
        "Billets de train",
        "Suivi sportif",
        "Suivi de forme quotidienne"
    ])

    if choix == "Billets de train":
        st.subheader("Billets et Carte Avantage")
        afficher_billets(user)

    if choix == "Suivi sportif":
        st.subheader("Suivi sportif")
        st.write("Renseigne ici ton activité du jour 👇")

        with st.form("form_activite"):
            sport = st.selectbox(
                "Sport pratiqué",
                ["⛹️‍♀️Basket", "🚴‍♂️Vélo", "🏃‍♂️Course à pied", "🏓Tennis de table",
                 "🏸Badminton", "🏊‍♂️Natation", "🏋️‍♂️Renforcement musculaire",
                 "⚽Football", "Autre"]
            )
            duree = st.text_input("⏱️Durée")
            difficulte = st.slider("Difficulté ressentie (😁 -> 🥵)", 1, 10, 5)
            plaisir = st.slider("Plaisir pris (😡 -> 🥰)", 1, 10, 5)
            date_activite = st.date_input("📅Date de l'activité", date.today(), format="DD/MM/YYYY")
            commentaire = st.text_area("🗣️Commentaires (si tu le souhaites)")
            submitted = st.form_submit_button("Enregistrer")

        if submitted:
            try:
                data = {
                    "joueuse_id": user["id"],
                    "sport": sport,
                    "duree": duree,
                    "difficulte": difficulte,
                    "plaisir": plaisir,
                    "commentaire": commentaire,
                    "date": date_activite.isoformat(),
                }
                supabase.table("activites").insert(data).execute()
                st.success("✅ Activité enregistrée avec succès !")
            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement : {e}")

        graph_suivi_sportif(st.session_state.user)

    elif choix == "Suivi de forme quotidienne":
        st.subheader("Suivi de forme quotidienne 🧘‍♀️")
        st.write("Évalue ton état général du jour 👇")

        with st.form("form_suivi_forme"):
            date_suivi = st.date_input("📅 Date du jour", date.today(), format="DD/MM/YYYY")
            fatigue = st.slider("😴 Fatigue générale (😊très frais -> 🫩toujours fatigué)", 1, 5, 3)
            sommeil = st.slider("🛌 Qualité du sommeil (👀insomnie -> 💤très reposant)", 1, 5, 3)
            douleur = st.slider("🤕 Douleurs (😎aucune douleur -> 😖très douloureux)", 1, 5, 3)
            stress = st.slider("😰 Niveau de stress (🧘‍♀️très détendu -> 😧très stressé)", 1, 5, 3)
            humeur = st.slider("😊 Humeur générale (😡contrarié, irritable, déprimé -> 🥳très positif)", 1, 5, 3)
            commentaire = st.text_area("🗣️ Commentaire (si tu le souhaites)")
            submitted = st.form_submit_button("Enregistrer")

        if submitted:
            try:
                data = {
                    "joueuse_id": user["id"],
                    "date": date_suivi.isoformat(),
                    "fatigue": fatigue,
                    "sommeil": sommeil,
                    "douleur": douleur,
                    "stress": stress,
                    "humeur": humeur,
                    "commentaire": commentaire,
                }
                supabase.table("suivi_forme").insert(data).execute()
                st.success("✅ Suivi enregistré avec succès !")
            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement : {e}")

        graph_suivi_forme(st.session_state.user)


def afficher_page_staff(user: dict):
    if user["numero_tel"] == os.getenv("MON_NUMERO"):
        if st.button("Mettre à jour les billets"):
            placeholder = st.empty()
            placeholder.info("Mise à jour en cours…")
            update_billets_from_storage()
            placeholder.success("Mise à jour terminée !")
            time.sleep(3)
            placeholder.empty()

    choix = st.radio("Que voulez-vous faire ?", [
        "Voir mes billets de train",
        "Consulter les suivis sportifs",
        "Consulter les suivis de forme quotidienne"
    ])

    if choix == "Voir mes billets de train":
        afficher_billets(user)

    elif choix == "Consulter les suivis sportifs":
        st.subheader("Suivi des joueuses")
        st.write("📊 Sélectionnez une joueuse pour consulter son suivi sportif.")

        try:
            query = supabase.table("joueuses").select("id, prenom, nom, categorie")

            if user.get("masculin") and not user.get("feminin"):
                query = query.eq("categorie", "Masculin")
            elif user.get("feminin") and not user.get("masculin"):
                query = query.eq("categorie", "Féminin")

            joueuses = query.order("prenom", desc=False).execute().data

        except Exception as e:
            st.error(f"Erreur lors du chargement des joueuses/joueurs : {e}")
            return

        if not joueuses:
            st.warning("Aucune joueuse trouvée dans la base de données.")
            return

        noms_joueuses = [f"{j['prenom']} {j['nom']}" for j in joueuses]
        choix_joueuse = st.selectbox("Choisissez une joueuse :", options=noms_joueuses)

        joueuse_selectionnee = next(
            (j for j in joueuses if f"{j['prenom']} {j['nom']}" == choix_joueuse), None
        )

        if joueuse_selectionnee:
            st.markdown(f"### 📈 Suivi de {choix_joueuse}")
            # Récupération des activités complètes
            activites = supabase.table("activites").select("*").eq("joueuse_id", joueuse_selectionnee["id"]).execute().data
            df_activites = pd.DataFrame(activites)
            
            if not df_activites.empty:
                legende = '''+1 : plus la difficulté augmente, plus le plaisir augmente  
                0 : aucune corrélation  
                -1 : plus la difficulté augmente, moins le plaisir est ressenti'''
                with st.expander("Légende"):
                    st.markdown(legende)
                corr = correlation_difficulte_plaisir(df_activites)
                st.markdown("**Corrélation Globale :** " + str(corr["correlation_globale"]))
                for sport, val in corr["correlation_par_sport"].items():
                    st.markdown(f"**{sport} :** {val}")
            graph_suivi_sportif(joueuse_selectionnee)

    elif choix == "Consulter les suivis de forme quotidienne":
        st.subheader("Suivi des joueuses")
        st.write("📊 Sélectionnez une joueuse pour consulter son suivi de forme quotidienne.")

        try:
            query = supabase.table("joueuses").select("id, prenom, nom, categorie")

            if user.get("masculin") and not user.get("feminin"):
                query = query.eq("categorie", "Masculin")
            elif user.get("feminin") and not user.get("masculin"):
                query = query.eq("categorie", "Féminin")

            joueuses = query.order("prenom", desc=False).execute().data

        except Exception as e:
            st.error(f"Erreur lors du chargement des joueuses/joueurs : {e}")
            return

        if not joueuses:
            st.warning("Aucune joueuse trouvée dans la base de données.")
            return

        noms_joueuses = [f"{j['prenom']} {j['nom']}" for j in joueuses]
        choix_joueuse = st.selectbox("Choisissez une joueuse :", options=noms_joueuses)

        joueuse_selectionnee = next(
            (j for j in joueuses if f"{j['prenom']} {j['nom']}" == choix_joueuse), None
        )

        if joueuse_selectionnee:
            st.markdown(f"### 📈 Suivi de {choix_joueuse}")
            # Récupération du suivi complet
            data = supabase.table("suivi_forme").select("*").eq("joueuse_id", joueuse_selectionnee["id"]).execute().data
            df_suivi = pd.DataFrame(data)
            
            if not df_suivi.empty:
                # Calcul charge normalisée
                df_suivi["charge"] = df_suivi.apply(compute_charge, axis=1)
                df_suivi["charge_norm"] = df_suivi["charge"].apply(normalize_charge)
            
                niveau_var, var_score = compute_variability(df_suivi)
                charge_moyenne = df_suivi["charge_norm"].mean()
                legende = '''Charge psycho-physiologique  
                0 : état très dégradé  
                100 : bien-être maximal'''
                with st.expander("Légende"):
                    st.markdown(legende)
                st.markdown(f"**Charge psycho-physiologique des 30 derniers jours :** {charge_moyenne:.2f}")
                if var_score is not None:
                    st.markdown(f"**Variabilité de la charge :** {niveau_var} ({round(var_score,2)})")
                else:
                    st.markdown(f"**Variabilité de la charge :** {niveau_var} (–)")

            graph_suivi_forme(joueuse_selectionnee)


# --- Page d'accueil ---
st.title("Pôle France Para Basketball Adapté")

# --- Zone de connexion ---
phone = st.text_input(
    "📱Entrez votre numéro de téléphone",
    placeholder="Ex: 0612345678"
).replace(" ", "")

numero = re.sub('\++33', '0', phone)

if st.button("🚪Accéder"):
    if len(numero) != 10 or not numero.startswith(("06", "07")):
        st.error("Numéro de téléphone invalide. Veuillez entrer un numéro français valide (10 chiffres, commence par 06 ou 07).")
    else:
        with st.spinner("Vérification en cours..."):
            user, type_user = verifier_utilisateur(numero)

            if user:
                st.session_state.user = user
                st.session_state.type_user = type_user
                st.rerun()
            else:
                st.error("Numéro inconnu.")

# --- Après identification ---
if st.session_state.user:
    st.success(f"Bienvenue {st.session_state.user['prenom']} !")

    if st.session_state.type_user == "joueuse":
        afficher_page_joueuse(st.session_state.user)
    else:
        afficher_page_staff(st.session_state.user)
