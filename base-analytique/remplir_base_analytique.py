#---------------------------------------------------------------------------------------------
# -------------- Remplir la base analytique (galaxie SQLite) avec la nuit --------------------

import pandas as pd
from pathlib import Path
import mysql.connector
from datetime import datetime
from pathlib import Path
import sqlite3


# =============================================================================
# CONFIGURATION
# =============================================================================

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
     "password": "passer",
    "database": "clinique_v2"
}

SQLITE_PATH = Path("base_analytique.db")

def get_id_temps_dim_temps(date_validation):
    SQLITE_PATH = Path("base_analytique.db")
    query = """
    SELECT * 
    FROM dim_temps 
    WHERE date_complete = ?
    """
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        df = pd.read_sql_query(query, conn, params=(date_validation,))
    finally:
        conn.close()
    return df


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


def pct_apnees_centrales(id_nuit):
    """
    Pourcentage d'apnées obstructives par rapport à toutes les apnées.
    """
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT
                COUNT(*) AS apnee_total,
                SUM(type_evenement = 'apnée obstructive') AS apnee_obstructive
            FROM evenement_respiratoire
            WHERE id_nuit = %s
              AND type_evenement IN (
                    'apnée obstructive',
                    'apnée centrale',
                    'apnée mixte'
              )
        """

        cursor.execute(query, (id_nuit,))
        row = cursor.fetchone()

        conn.close()

        if row is None:
            return 0

        total = row[0] or 0
        obstructives = row[1] or 0

        if total == 0:
            return 0

        return round(obstructives * 100 / total, 2)

    except Exception as e:
        print(f"Erreur MySQL : {e}")
        return None

print(f"get_id_temps_dim_temps : {get_id_temps_dim_temps('2023-09-30').iloc[0]["id_temps"]}")
print(f"get_id_suivi_le_plus_proche_dim_suivi_patient : {get_id_suivi_le_plus_proche_dim_suivi_patient(1).iloc[0]["id_suivi"]}")
print(f"pct_apnees_centrales: {pct_apnees_centrales(1)}")

def remplir_base_analytique(detail):
    SQLITE_PATH = Path("base_analytique.db")

    if detail.empty:
        return

    # Première ligne du DataFrame
    ligne = detail.iloc[0]
    
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()
    
    print("id_nuit :", ligne["id_nuit"])
    print("id_patient :", ligne["id_patient"])
    print("date_nuit :", ligne["date_nuit"])
    print("iah :", ligne["iah"])
    print("severite_iah :", ligne["severite_iah"])
    print("spo2_min :", ligne["spo2_min"])
    print("spo2_moy :", ligne["spo2_moy"])
    print("spo2_mediane :", ligne["spo2_mediane"])
    print("nb_apnees :", ligne["nb_apnees"])
    print("nb_hypopnees :", ligne["nb_hypopnees"])
    print("nb_rera :", ligne["nb_rera"])
    print("nb_microeveils :", ligne["nb_microeveils"])
    print("duree_sommeil_min :", ligne["duree_sommeil_min"])
    print("duree_hypoxie_min :", ligne["duree_hypoxie_min"])
    print("position_dominante :", ligne["position_dominante"])
    print("decibels_max :", ligne["decibels_max"])
    print("decibels_moy :", ligne["decibels_moy"])
    print("nb_ronflements_forts :", ligne["nb_ronflements_forts"])
    
    query = """
    INSERT INTO faits_nuits (
        id_nuit,
        id_patient,
        id_temps,
        iah,
        severite_iah,
        spo2_min,
        spo2_moy,
        spo2_mediane,
        nb_apnees,
        nb_hypopnees,
        nb_rera,
        nb_microeveils,
        duree_sommeil_min,
        duree_hypoxie_min,
        position_dominante,
        decibels_max,
        decibels_moy,
        nb_ronflements_forts,
        id_suivi_le_plus_proche,
        pct_apnees_centrales
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    cursor.execute(query, (
        ligne["id_nuit"],
        ligne["id_patient"],
        452254,
        ligne["iah"],
        ligne["severite_iah"],
        ligne["spo2_min"],
        ligne["spo2_moy"],
        ligne["spo2_mediane"],
        ligne["nb_apnees"],
        ligne["nb_hypopnees"],
        ligne["nb_rera"],
        ligne["nb_microeveils"],
        ligne["duree_sommeil_min"],
        ligne["duree_hypoxie_min"],
        ligne["position_dominante"],
        ligne["decibels_max"],
        ligne["decibels_moy"],
        ligne["nb_ronflements_forts"],
        1 ,
       100 # % nb_apnees obstructive par rapport aux autres apbnées dans la table evenement_respiratoire
    ))
    conn.commit()
    conn.close()
    
#remplir_base_analytique(detail)

