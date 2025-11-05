from supabase_client import supabase
import pdfplumber
from rapidfuzz import fuzz
from io import BytesIO
import unicodedata
import re

def normalize(s: str) -> str:
    """
    Met en minuscules, enlève accents, apostrophes, espaces et caractères spéciaux.
    """
    s = s.lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z]', '', s)
    return s

def update_billets_from_storage(bucket_name="Billets", score_threshold=70):
    """
    Parcourt tous les PDFs du bucket Supabase 'Billets', extrait le texte,
    associe le fichier à une joueuse ou un staff (UUID), et met à jour
    la table 'billets' uniquement si le fichier n'existe pas déjà.
    """

    # Récupérer toutes les joueuses et le staff
    joueurs = supabase.table("joueuses").select("*").execute().data
    staffs = supabase.table("staff").select("*").execute().data

    # Lister les fichiers du bucket
    files = supabase.storage.from_(bucket_name).list()
    if not files:
        print("Aucun fichier trouvé dans le bucket.")
        return

    for f in files:
        filename = f["name"]

        try:
            file_bytes = supabase.storage.from_(bucket_name).download(filename)
        except Exception as e:
            print(f"Erreur téléchargement {filename}: {e}")
            continue

        pdf_file = BytesIO(file_bytes)
        text = ""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Erreur lecture PDF {filename}: {e}")
            continue

        pdf_words = [normalize(w) for w in text.split()]

        # Chercher la meilleure correspondance parmi toutes les personnes
        best_match = None
        best_score = 0

        # Joueurs
        for j in joueurs:
            prenom_norm = normalize(j['prenom'])
            nom_norm = normalize(j['nom'])
            score_prenom = max([fuzz.ratio(prenom_norm, w) for w in pdf_words])
            score_nom = max([fuzz.ratio(nom_norm, w) for w in pdf_words])
            total_score = (score_prenom + score_nom) / 2
            if total_score > best_score:
                best_score = total_score
                best_match = j

        # Staff
        for s in staffs:
            prenom_norm = normalize(s['prenom'])
            nom_norm = normalize(s['nom'])
            score_prenom = max([fuzz.ratio(prenom_norm, w) for w in pdf_words])
            score_nom = max([fuzz.ratio(nom_norm, w) for w in pdf_words])
            total_score = (score_prenom + score_nom) / 2
            if total_score > best_score:
                best_score = total_score
                best_match = s

        # Vérifier si le score est suffisant
        if best_score >= score_threshold and best_match is not None:
            # Utiliser UUID de la personne (joueuse ou staff)
            personne_id = best_match.get("id")

            # Vérifier si le billet existe déjà
            existing = supabase.table("billets").select("*")\
                .eq("nom_fichier", filename).execute().data

            if not existing:
                supabase.table("billets").insert({
                    "joueuse_id": personne_id,
                    "nom_fichier": filename,
                    "url_stockage": filename  # ou l’URL complète si nécessaire
                }).execute()
                print(f"Billet ajouté pour {best_match['prenom']} {best_match['nom']}")
            else:
                print(f"Billet déjà existant : {best_match['prenom']} - {filename}")
        else:
            print(f"Aucune correspondance fiable pour {filename}")
    update_billets_db()


def update_billets_db():

    bucket_name = "Billets"
    billets_db = supabase.table("billets").select("nom_fichier").execute().data

    existing_filenames = {b["nom_fichier"] for b in billets_db}
    files = supabase.storage.from_(bucket_name).list()

    current_storage_files = {f["name"] for f in files if f["name"].endswith(".pdf")}

    # --- 1️⃣ Nettoyage : suppression des billets absents du storage ---
    missing_files = existing_filenames - current_storage_files
    for missing in missing_files:
        supabase.table("billets").delete().eq("nom_fichier", missing).execute()
        print(f"🗑️ Supprimé {missing} (absent du storage)")

    # --- 2️⃣ Boucle principale : ajout / mise à jour ---
    for f in files:
        if not f["name"].endswith(".pdf"):
            continue

        filename = f["name"]
        url = supabase.storage.from_(bucket_name).get_public_url(filename)

        # Vérifie si le billet existe déjà
        existing = supabase.table("billets").select("*").eq("nom_fichier", filename).execute().data
        if existing:
            continue  # on ne duplique pas

        # Télécharge le PDF pour analyse (lecture texte)
        pdf_bytes = supabase.storage.from_(bucket_name).download(filename)
        reader = PdfReader(BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        # Nettoyage du texte
        def normalize(s):
            s = s.upper()
            s = unicodedata.normalize("NFD", s)
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            return s.replace(" ", "").replace("-", "")

        text_norm = normalize(text)

        # Recherche joueuse
        joueuses = supabase.table("joueuses").select("id, prenom, nom").execute().data
        staff = supabase.table("staff").select("id, prenom, nom").execute().data

        best_match = None
        best_score = 0

        for person in joueuses + staff:
            nom = normalize(person["nom"])
            prenom = normalize(person["prenom"])
            score = (nom in text_norm) + (prenom in text_norm)
            if score > best_score:
                best_score = score
                best_match = person

        if best_match and best_score >= 1:
            supabase.table("billets").insert({
                "joueuse_id": best_match["id"],  # même clé pour staff, peu importe
                "stage_id": None,
                "nom_fichier": filename,
                "url_stockage": url,
            }).execute()
            print(f"✅ Ajouté : {filename} → {best_match['prenom']} {best_match['nom']}")
        else:
            print(f"⚠️ Aucun match trouvé pour {filename}")

    print("🧹 Nettoyage terminé : base billets synchronisée avec le storage.")
