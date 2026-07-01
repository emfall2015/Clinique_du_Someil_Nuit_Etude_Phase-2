import pandas as pd
#-------------------------------------------------------------------------------------
#                                   Lecture CSV
#-------------------------------------------------------------------------------------
df = pd.read_csv('signal-cpap-patient-2-062026.csv', sep=",", encoding="utf-8-sig")

#-------------------------------------------------------------------------------------
#                                Calcul d'indicateur
#-------------------------------------------------------------------------------------
# Calcul de l'alerte relative à l'utilisation du masque    
df['alerte_observance_insuffisante'] = 0
df.loc[df['duree_utilisation_h'] < 4, ['alerte_observance_insuffisante']] = 1

# Calcul de l'alerte relative à l'IAH résiduel  
df['alerte_iah_eleve'] = 0
df.loc[df['iah_residuel'] > 5, ['alerte_iah_eleve']] = 1

#-------------------------------------------------------------------------------------
#               Chargement des données dans la base analystique
#-------------------------------------------------------------------------------------

from pathlib import Path
import mysql.connector
from datetime import datetime
from pathlib import Path
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
# =============================================================================
# CONFIGURATION
# =============================================================================
MYSQL_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

SQLITE_PATH = Path("base_analytique.db")

"""
Récuperer id_temps dans dim_temps si il existe, sinon creer la ligne sur dim_temps
"""


def get_or_create_dim_temps(date_nuit):
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    # 1. vérifier existence
    query = "SELECT id_temps FROM dim_temps WHERE date_complete = ?"
    df = pd.read_sql_query(query, conn, params=(date_nuit,))

    if not df.empty:
        conn.close()
        return int(df.iloc[0]["id_temps"])

    # 2. sinon créer la dimension
    if isinstance(date_nuit, str):
        dt = datetime.strptime(date_nuit, "%Y-%m-%d").date()
    else:
        dt = date_nuit  # déjà datetime.date

    id_temps = int(dt.strftime("%Y%m%d"))  # conversion 20260701 exemple
    annee = dt.year
    mois = dt.month
    jour = dt.day

    # Calcul du trimestre
    # T1 : janvier, février, mars
    # T2 : avril, mai, juin
    # T3 : juillet, août, septembre
    # T4 : octobre, novembre, décembre
    trimestre = (mois - 1) // 3 + 1

    jours_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

    jour_semaine = jours_fr[dt.weekday()]
    # dt.weekday retourne le jour de la semaine en commencant par 0
    # 0 lundi,
    # 1 Mardi
    # 2 Mercredi
    est_weekend = 1 if dt.weekday() >= 5 else 0

    insert_query = """
    INSERT INTO dim_temps (
        id_temps,
        date_complete,
        annee,
        mois,
        jour,
        trimestre,
        jour_semaine,
        est_weekend
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    cursor.execute(
        insert_query,
        (id_temps, date_nuit, annee, mois, jour, trimestre, jour_semaine, est_weekend),
    )

    conn.commit()
    conn.close()

    return id_temps


def get_id_suivi_le_plus_proche_dim_suivi_patient(id_patient):
    SQLITE_PATH = Path("base_analytique.db")
    query = """
        SELECT *
        FROM dim_suivi_patient
        WHERE id_patient = ?
        ORDER BY date_suivi DESC
        LIMIT 1;
        """
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        df = pd.read_sql_query(query, conn, params=(id_patient,))
    finally:
        conn.close()
    return df


def remplir_base_analytique(detail):
    SQLITE_PATH = Path("base_analytique.db")

    if detail.empty:
        return

    # Première ligne du DataFrame
    ligne = detail.iloc[0]
    #print(ligne)
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    query = """
INSERT INTO faits_suivi_cpap_jour (
    id_suivi_source,
    id_patient,
    id_temps,
    duree_utilisation_h,
    iah_residuel,
    fuite_l_min,
    nb_evenements,
    qualite_donnee,
    id_suivi_le_plus_proche,
    alerte_orbservance_insuffisante,
    alerte_iah_eleve,
)

VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )

ON CONFLICT(id_nuit) DO UPDATE SET
    id_patient = excluded.id_patient,
    id_temps = excluded.id_temps,
    iah = excluded.iah,
    severite_iah = excluded.severite_iah,
    spo2_min = excluded.spo2_min,
    spo2_moy = excluded.spo2_moy,
    spo2_mediane = excluded.spo2_mediane,
    nb_apnees = excluded.nb_apnees,
    nb_hypopnees = excluded.nb_hypopnees,
    nb_rera = excluded.nb_rera,
    nb_microeveils = excluded.nb_microeveils,
    duree_sommeil_min = excluded.duree_sommeil_min,
    duree_hypoxie_min = excluded.duree_hypoxie_min,
    position_dominante = excluded.position_dominante,
    decibels_max = excluded.decibels_max,
    decibels_moy = excluded.decibels_moy,
    nb_ronflements_forts = excluded.nb_ronflements_forts,
    id_suivi_le_plus_proche = excluded.id_suivi_le_plus_proche,
    pct_apnees_centrales = excluded.pct_apnees_centrales
"""

    cursor.execute(
        query,
        (
            int(ligne["id_nuit"]),
            int(ligne["id_patient"]),
            int(get_or_create_dim_temps(ligne["date_nuit"])),
            float(ligne["iah"]),
            str(ligne["severite_iah"]),
            float(ligne["spo2_min"]),
            float(ligne["spo2_moy"]),
            float(ligne["spo2_mediane"]),
            int(ligne["nb_apnees"]),
            int(ligne["nb_hypopnees"]),
            int(ligne["nb_rera"]),
            int(ligne["nb_microeveils"]),
            float(ligne["duree_sommeil_min"]),
            float(ligne["duree_hypoxie_min"]),
            str(ligne["position_dominante"]),
            float(ligne["decibels_max"]),
            float(ligne["decibels_moy"]),
            int(ligne["nb_ronflements_forts"]),
            int(
                get_id_suivi_le_plus_proche_dim_suivi_patient(
                    int(ligne["id_patient"])
                ).iloc[0]["id_suivi"]
            ),
            float(pct_apnees_centrales(int(ligne["id_nuit"]))),
        ),
    )
    conn.commit()
    conn.close()
