import pandas as pd
from pathlib import Path
import mysql.connector
from datetime import datetime
from pathlib import Path
import sqlite3
import os
from dotenv import load_dotenv


#-------------------------------------------------------------------------------------
#                                   Lecture CSV
#-------------------------------------------------------------------------------------
filename = "./base-analytique/csv_cpap/signal-cpap-patient-2-062026.csv"

df = pd.read_csv(filename, sep=",", encoding="utf-8-sig")

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
#                               Obtenir l'ID patient
#-------------------------------------------------------------------------------------
partie_nom_fichier = filename.split("-")

id_patient = partie_nom_fichier[4]


#-------------------------------------------------------------------------------------
#               Chargement des données dans la base analytique
#-------------------------------------------------------------------------------------

load_dotenv()
# =============================================================================
# CONFIGURATION
# =============================================================================
cnx = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
SQLITE_PATH = Path("./base-analytique/base_analytique.db")

"""
Récuperer id_temps dans dim_temps si il existe, sinon creer la ligne sur dim_temps
"""


def get_or_create_dim_temps(date_jour):
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    # 1. vérifier existence
    query = "SELECT id_temps FROM dim_temps WHERE date_complete = ?"
    data = pd.read_sql_query(query, conn, params=(date_jour,))

    if not data.empty:
        conn.close()
        return int(data.iloc[0]["id_temps"])

    # 2. sinon créer la dimension
    if isinstance(date_jour, str):
        dt = datetime.strptime(date_jour, "%Y-%m-%d").date()
    else:
        dt = date_jour  # déjà datetime.date

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
        (id_temps, date_jour, annee, mois, jour, trimestre, jour_semaine, est_weekend),
    )

    conn.commit()
    conn.close()

    return id_temps




def get_id_suivi_le_plus_proche_dim_suivi_patient(id_patient):
    query = """
        SELECT *
        FROM dim_suivi_patient
        WHERE id_patient = ?
        ORDER BY date_suivi DESC
        LIMIT 1;
        """
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        data = pd.read_sql_query(query, conn, params=(id_patient,))
    finally:
        conn.close()
    return int(data.iloc[0]["id_suivi"])




def get_id_suivi_source(id_appareil,date_jour,duree_utilisation_h,iah_residuel,fuites_l_min,nb_evenements,qualite_donnee):
    cur = cnx.cursor()
    query = """
        SELECT id_suivi FROM suivi_cpap_jour WHERE date_jour = %s
"""
    id_suivi_source = pd.read_sql_query(query, cnx, params=(date_jour,))

        # 1. vérifier existence    
    if not id_suivi_source.empty:
        return int(id_suivi_source.iloc[0]["id_suivi"])
    
        # 2. sinon créer la dimension
    if isinstance(date_jour, str):
        dt = datetime.strptime(date_jour, "%Y-%m-%d").date()
    else:
        dt = date_jour

    insert_query = """
        INSERT INTO suivi_cpap_jour (
            id_appareil,
            date_jour,
            duree_utilisation_h,
            iah_residuel,
            fuites_l_min,
            nb_evenements,
            qualite_donnee
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
    
    cur.execute(
            insert_query,
            (id_appareil, date_jour, duree_utilisation_h, iah_residuel, fuites_l_min, nb_evenements, qualite_donnee),
        )
    cnx.commit()
    
    query_select = "SELECT LAST_INSERT_ID() as id_suivi"
    id_suivi_source = pd.read_sql_query(query_select, cnx)


    return int(id_suivi_source.iloc[0]["id_suivi"])

    




def remplir_base_analytique(id_appareil, date_jour, duree_utilisation_h, iah_residuel, fuites_l_min, nb_evenements, qualite_donnee, alerte_observance_insuffisante, alerte_iah_eleve, id_patient):

    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    query = """
INSERT INTO faits_suivi_cpap_jour (
    id_suivi_source,
    id_patient,
    id_temps,
    duree_utilisation_h,
    iah_residuel,
    fuites_l_min,
    nb_evenements,
    qualite_donnee,
    id_suivi_le_plus_proche,
    alerte_observance_insuffisante,
    alerte_iah_eleve
)

VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )

"""

    cursor.execute(
        query,
        (
            int(get_id_suivi_source(id_appareil,date_jour,duree_utilisation_h,iah_residuel,fuites_l_min,nb_evenements,qualite_donnee)),
            int(id_patient),
            int(get_or_create_dim_temps(date_jour)),
            float(duree_utilisation_h),
            float(iah_residuel),
            float(fuites_l_min),
            int(nb_evenements),
            str(qualite_donnee),
            str(get_id_suivi_le_plus_proche_dim_suivi_patient(id_patient)),
            int(alerte_observance_insuffisante),
            int(alerte_iah_eleve)
        )
    )
    conn.commit()
    conn.close()


for _, detail in df.iterrows():
    id_appareil = detail['id_appareil']
    date_jour = detail['date_jour']
    duree_utilisation_h = detail["duree_utilisation_h"]
    iah_residuel = detail['iah_residuel']
    fuites_l_min = detail['fuites_l_min']
    nb_evenements = detail['nb_evenements']
    qualite_donnee = detail['qualite_donnee']
    alerte_observance_insuffisante = detail['alerte_observance_insuffisante']
    alerte_iah_eleve = detail['alerte_iah_eleve']

    remplir_base_analytique(id_appareil, date_jour, duree_utilisation_h, iah_residuel, fuites_l_min, nb_evenements, qualite_donnee, alerte_observance_insuffisante, alerte_iah_eleve, id_patient)

cnx.close()