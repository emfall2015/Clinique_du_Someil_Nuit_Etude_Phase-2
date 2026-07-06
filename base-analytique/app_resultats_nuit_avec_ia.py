"""
Application Streamlit pour les résultats des nuits avec prédiction de comorbidités
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import mysql.connector
from datetime import datetime

# Import génération PDF
from generation_pdf import generer_pdf_patient

# Import du module IA
from ia_comorbidites import get_comorbidite_probable, afficher_prediction_comorbidites
from remplir_base_analytique import remplir_base_analytique

import os
from dotenv import load_dotenv

load_dotenv()

# ====================== CONFIG ======================

st.set_page_config(
    page_title="Clinique du Sommeil",
    layout="wide"
)

st.title("Résultats des Nuits d'Étude")
st.markdown("**Clinique du Sommeil d'Arles**")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

NUITS_DIR = Path("../nuits")

# ====================== CHARGEMENT DES DONNÉES ======================

@st.cache_data
def get_resultats(id_nuit=None):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        query = "CALL sp_lire_resultat_nuit(%s);"

        df = pd.read_sql(
            query,
            conn,
            params=[id_nuit]
        )

        conn.close()
        return df

    except Exception as e:
        st.error(f"Erreur BDD : {e}")
        return pd.DataFrame()


@st.cache_data
def get_liste_nuits():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        df = pd.read_sql(
            """
            SELECT 
                n.id_nuit,
                p.id_patient,
                p.nom,
                p.prenom,
                n.date_nuit,
                r.iah,
                r.severite_iah
            FROM nuit_etude n
            JOIN patient p ON p.id_patient = n.id_patient
            JOIN resultat_nuit r ON r.id_nuit = n.id_nuit
            ORDER BY n.date_nuit DESC
            """,
            conn
        )

        conn.close()
        return df

    except Exception as e:
        st.error(f"Erreur liste nuits : {e}")
        return pd.DataFrame()


df_liste = get_liste_nuits()

# ====================== INTERFACE ======================

if not df_liste.empty:

    search = st.text_input("Rechercher patient", "")
    filtered = df_liste.copy()

    if search:
        filtered = filtered[
            filtered['nom'].str.contains(search, case=False, na=False)
            |
            filtered['prenom'].str.contains(search, case=False, na=False)
        ]

    st.subheader(f"Nuits trouvées : {len(filtered)}")

    if not filtered.empty:

        st.dataframe(filtered, use_container_width=True, hide_index=True)

        selected_id = st.selectbox(
            "Sélectionner une nuit",
            options=filtered['id_nuit'].tolist(),
            format_func=lambda x:
                f"Nuit {x} : "
                f"{filtered[filtered['id_nuit']==x]['nom'].iloc[0]} "
                f"{filtered[filtered['id_nuit']==x]['prenom'].iloc[0]}"
        )

        selected_patient_id = filtered[
            filtered['id_nuit'] == selected_id
        ]['id_patient'].iloc[0]

        detail = get_resultats(selected_id)

        # ====================== SI DETAIL OK ======================

        if not detail.empty:

            # ====================== IA ======================

            st.markdown("---")
            st.header("Analyse IA : Comorbidités Probables")

            comorbidite, probabilite, toutes_predictions = get_comorbidite_probable(
                id_nuit=selected_id,
                id_patient=selected_patient_id
            )

            if comorbidite:

                col1, col2 = st.columns([3, 1])

                with col1:
                    st.subheader("Comorbidité la plus probable")

                with col2:
                    if probabilite >= 0.7:
                        st.error(f"{probabilite*100:.1f}%")
                    elif probabilite >= 0.5:
                        st.warning(f"{probabilite*100:.1f}%")
                    else:
                        st.success(f"{probabilite*100:.1f}%")

                st.metric(
                    label="Diagnostic IA",
                    value=comorbidite,
                    delta=f"Confiance : {probabilite*100:.1f}%"
                )

                if st.button("Voir toutes les prédictions de comorbidités"):
                    afficher_prediction_comorbidites(int(selected_patient_id))

            else:
                st.info("Pas assez de données pour la prédiction IA.")

            st.markdown("---")

            # ====================== RAPPORT ======================

            rapport_path = NUITS_DIR / str(selected_id) / f"rapport_medical_{selected_id}.txt"

            if rapport_path.exists():
                st.subheader("Rapport médical complet")
                rapport = rapport_path.read_text(encoding="utf-8")
                st.text_area("", rapport, height=450)
            else:
                rapport = ""
                st.warning(f"Rapport non trouvé pour la nuit {selected_id}")

            # ====================== COURBES ======================

            st.subheader("Courbes de la nuit")

            nuit_dir = NUITS_DIR / str(selected_id)

            col1, col2, col3 = st.columns(3)

            images = [
                (f"spo2_{selected_id}.png", "SpO₂"),
                (f"debit_nasal_nuit_{selected_id}.png", "Débit Nasal"),
                (f"ronflement_db_{selected_id}.png", "Ronflements"),
            ]

            for col, (img, title) in zip([col1, col2, col3], images):
                path = nuit_dir / img
                with col:
                    if path.exists():
                        col.image(str(path), caption=title, use_container_width=True)
                    else:
                        col.warning(f"{img} manquant")

            # ====================== VALIDATION ======================

            st.markdown("---")
            st.subheader("✅ Validation")

            if not comorbidite:
                comorbidite = "Aucune prédiction disponible"
                probabilite = 0

            if st.button("Valider"):

                with st.spinner("Remplissage de la base analytique..."):
                    remplir_base_analytique(detail)

                st.success("✅ Base analytique remplie avec succès.")

                patient = filtered[
                    filtered['id_nuit'] == selected_id
                ].iloc[0]

                fichier_pdf = generer_pdf_patient(
                    patient,
                    detail,
                    rapport,
                    comorbidite,
                    probabilite,
                    nuit_dir
                )

                st.success("📄 PDF généré avec succès.")

                with open(fichier_pdf, "rb") as pdf:
                    st.download_button(
                        label="⬇️ Télécharger le PDF",
                        data=pdf,
                        file_name=fichier_pdf,
                        mime="application/pdf"
                    )

        else:
            st.error("Impossible de charger le détail de la nuit.")

    else:
        st.warning("Aucune nuit trouvée dans la base.")

else:
    st.warning("Aucune nuit trouvée dans la base.")

st.sidebar.caption(
    f"Actualisé : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)