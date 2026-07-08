import pandas as pd
import mysql.connector
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
import csv
import sqlite3
import sys

# -----------------------------------------------------
# PARAMÈTRES
# -----------------------------------------------------
id_nuit = sys.argv[1]
id_medecin = sys.argv[2]
commentaire_medical = sys.argv[3]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
TRAITE_DIR = os.path.join(RAW_DIR, "traite")

os.makedirs(TRAITE_DIR, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")

# -----------------------------------------------------
# CHARGEMENT CSV
# -----------------------------------------------------
csv_file = None
for fichier in os.listdir(RAW_DIR):
    if fichier.endswith(f"-{id_nuit}.csv"):
        csv_file = os.path.join(RAW_DIR, fichier)
        df = pd.read_csv(csv_file)
        break
else:
    raise FileNotFoundError(f"Aucun fichier trouvé pour l'id_nuit={id_nuit}")

df["timestamp_sec"] = pd.to_numeric(df["timestamp_sec"], errors="coerce")
df["spo2"] = pd.to_numeric(df["spo2"], errors="coerce")
df["debit_nasal_pct"] = pd.to_numeric(df["debit_nasal_pct"], errors="coerce")
df["effort_thoracique_pct"] = pd.to_numeric(df["effort_thoracique_pct"], errors="coerce")
df["ronflements_db"] = pd.to_numeric(df["ronflements_db"], errors="coerce")
df["flag_evenement"] = pd.to_numeric(df["flag_evenement"], errors="coerce")
df["position"] = df["position"].astype(str).str.strip()

df = df.sort_values("timestamp_sec").reset_index(drop=True)

# -----------------------------------------------------
# CALCULS
# -----------------------------------------------------
pas_sec = df["timestamp_sec"].iloc[1] - df["timestamp_sec"].iloc[0]
duree_sommeil_sec = df["timestamp_sec"].iloc[-1] - df["timestamp_sec"].iloc[0] + pas_sec
duree_sommeil_min = duree_sommeil_sec / 60

spo2_min = df["spo2"].min()
spo2_moy = round(df["spo2"].mean(), 1)
spo2_mediane = round(df["spo2"].median(), 1)

decibels_max = df["ronflements_db"].max()
decibels_moy = round(df["ronflements_db"].mean(), 1)

duree_hypoxie = len(df.loc[df["spo2"] < 90]) * 10
nbr_ronflements_forts = int((df["ronflements_db"] > 70).sum())

position_dominante = df["position"].value_counts().idxmax()

# -----------------------------------------------------
# CONNEXION MYSQL
# -----------------------------------------------------
load_dotenv()

cnx = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cur = cnx.cursor()

cur.callproc(
    "insert_data_night",
    (
        id_nuit,
        id_medecin,
        spo2_min,
        spo2_moy,
        spo2_mediane,
        duree_sommeil_min,
        duree_hypoxie,
        position_dominante,
        decibels_max,
        decibels_moy,
        nbr_ronflements_forts,
        commentaire_medical,
    ),
)
cnx.commit()

# -----------------------------------------------------
# DETECTION INTERVALLES EVENEMENTS
# -----------------------------------------------------
temps_debut = None
intervalles_detectes = []

for _, row in df.iterrows():
    flag = row["flag_evenement"]
    timestamp = row["timestamp_sec"]

    if pd.isna(flag) or pd.isna(timestamp):
        continue

    try:
        flag_int = int(flag)
        timestamp_int = int(timestamp)
    except ValueError:
        continue

    if flag_int == 1 and temps_debut is None:
        temps_debut = timestamp_int / 10
    elif flag_int == 0 and temps_debut is not None:
        temps_fin = (timestamp_int - 10) / 10
        intervalles_detectes.append((temps_debut, temps_fin))
        temps_debut = None

# -----------------------------------------------------
# SAUVEGARDE CSV TRAITE
# -----------------------------------------------------
chemin_fichier = os.path.join(TRAITE_DIR, f"traite_signal-psg-patient-2-nuit-{id_nuit}.csv")
df.to_csv(chemin_fichier, sep=",", index=False, encoding="utf-8-sig")

# -----------------------------------------------------
# GRAPHES 3 PNG + 3 PDF
# -----------------------------------------------------
dossier = os.path.join(BASE_DIR, "nuits", str(id_nuit))
os.makedirs(dossier, exist_ok=True)

def formatter_figure(ax, titre, ylabel):
    ax.set_title(titre, fontsize=14, fontweight="bold", pad=14)
    ax.set_xlabel("Temps (/10 s)", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=9)

def appliquer_intervalles(ax):
    for debut, fin in intervalles_detectes:
        ax.axvspan(debut, fin, color="green", alpha=0.12)

x = df["timestamp_sec"] / 10

# 1) Débit nasal
fig1, ax1 = plt.subplots(figsize=(18, 5))
ax1.plot(x, df["debit_nasal_pct"], color="#1f77b4", linewidth=1.2, label="Débit nasal")
appliquer_intervalles(ax1)
formatter_figure(ax1, "Courbe 1 — Évolution du débit nasal", "Débit nasal (%)")
ax1.legend(loc="upper right")
fig1.tight_layout(pad=2.5)
fig1.savefig(os.path.join(dossier, f"debit_nasal_nuit_{id_nuit}.png"), dpi=300, bbox_inches="tight")
fig1.savefig(os.path.join(dossier, f"debit_nasal_nuit_{id_nuit}.pdf"), dpi=300, bbox_inches="tight")
plt.close(fig1)

# 2) Ronflements
fig2, ax2 = plt.subplots(figsize=(18, 5))
ax2.plot(x, df["ronflements_db"], color="#d62728", linewidth=1.2, label="Ronflements")
ax2.axhline(70, color="orange", linestyle="--", linewidth=1.2, label="Seuil 70 dB")
appliquer_intervalles(ax2)
formatter_figure(ax2, "Courbe 2 — Évolution des ronflements", "Ronflement (dB)")
ax2.legend(loc="upper right")
fig2.tight_layout(pad=2.5)
fig2.savefig(os.path.join(dossier, f"ronflement_db_{id_nuit}.png"), dpi=300, bbox_inches="tight")
fig2.savefig(os.path.join(dossier, f"ronflement_db_{id_nuit}.pdf"), dpi=300, bbox_inches="tight")
plt.close(fig2)

# 3) SpO2
fig3, ax3 = plt.subplots(figsize=(18, 5))
ax3.plot(x, df["spo2"], color="#2c7fb8", linewidth=1.2, label="SpO2")
ax3.axhline(90, color="red", linestyle="--", linewidth=1.2, label="Seuil 90%")
ax3.fill_between(x, df["spo2"], 90, where=(df["spo2"] < 90), color="red", alpha=0.10)
appliquer_intervalles(ax3)
formatter_figure(ax3, "Courbe 3 — Évolution de la saturation en oxygène", "SpO2 (%)")
ax3.legend(loc="lower left")
fig3.tight_layout(pad=2.5)
fig3.savefig(os.path.join(dossier, f"spo2_{id_nuit}.png"), dpi=300, bbox_inches="tight")
fig3.savefig(os.path.join(dossier, f"spo2_{id_nuit}.pdf"), dpi=300, bbox_inches="tight")
plt.close(fig3)

# -----------------------------------------------------
# RAPPORT MEDICAL
# -----------------------------------------------------
cur.execute(
    """
    SELECT nb_apnees, nb_hypopnees, nb_rera, iah, nb_microeveils, duree_hypoxie_min
    FROM resultat_nuit
    WHERE id_nuit = %s
    """,
    (id_nuit,),
)
result = cur.fetchone()

if result:
    nb_apnees, nb_hypopnees, nb_rera, iah, nb_microeveils, duree_hypoxie_min = result
else:
    nb_apnees = nb_hypopnees = nb_rera = iah = nb_microeveils = duree_hypoxie_min = 0

with open(os.path.join(dossier, f"rapport_medical_{id_nuit}.txt"), "w", encoding="utf-8") as f:
    f.write("=== Rapport médical ===\n\n")
    f.write(f"Nuit : {id_nuit}\n")
    f.write(f"Médecin : {id_medecin}\n\n")
    f.write(f"SpO2 min : {spo2_min}\n")
    f.write(f"SpO2 moy : {spo2_moy}\n")
    f.write(f"SpO2 médiane : {spo2_mediane}\n\n")
    f.write(f"Ronflements forts (>70 dB) : {nbr_ronflements_forts}\n")
    f.write(f"Ronflements max : {decibels_max}\n")
    f.write(f"Ronflements moy : {decibels_moy}\n\n")
    f.write(f"Durée hypoxie : {duree_hypoxie} sec\n")
    f.write(f"Position dominante : {position_dominante}\n\n")
    f.write(f"Apnées : {nb_apnees}\n")
    f.write(f"Hypopnées : {nb_hypopnees}\n")
    f.write(f"RERA : {nb_rera}\n")
    f.write(f"IAH : {iah}\n")
    f.write(f"Commentaire : {commentaire_medical}\n")

# -----------------------------------------------------
# DATALAKE SQLITE
# -----------------------------------------------------
datalake = os.path.join(BASE_DIR, "datalake")
os.makedirs(datalake, exist_ok=True)

db_path = os.path.join(datalake, "datalake.db")
cnx_sqlite = sqlite3.connect(db_path)
cursqlite = cnx_sqlite.cursor()

cursqlite.execute("""
CREATE TABLE IF NOT EXISTS raw_capteur (
    id_raw INTEGER PRIMARY KEY AUTOINCREMENT,
    id_nuit INTEGER NOT NULL,
    timestamp_sec INTEGER NOT NULL,
    spo2 REAL,
    debitnasalpct REAL,
    effortthoraciquepct REAL,
    position TEXT,
    ronflements_db REAL,
    flagevenement INTEGER CHECK (flagevenement IN (0,1))
)
""")

cursqlite.execute("""
CREATE TABLE IF NOT EXISTS curated_nuit (
    id_curated INTEGER PRIMARY KEY AUTOINCREMENT,
    id_nuit INTEGER NOT NULL,
    spo2_min REAL,
    spo2_moy REAL,
    spo2_mediane REAL,
    nb_apnees INTEGER,
    nb_hypopnees INTEGER,
    nb_rera INTEGER,
    nb_microeveils INTEGER,
    dureehypoxiemin REAL,
    position_dominante TEXT,
    decibels_max REAL,
    decibels_moy REAL,
    nbronflementsforts INTEGER
)
""")

for _, row in df.iterrows():
    cursqlite.execute(
        """
        INSERT INTO raw_capteur (
            id_nuit, timestamp_sec, spo2, debitnasalpct,
            effortthoraciquepct, position, ronflements_db, flagevenement
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id_nuit,
            row["timestamp_sec"],
            row["spo2"],
            row["debit_nasal_pct"],
            row["effort_thoracique_pct"],
            row["position"],
            row["ronflements_db"],
            row["flag_evenement"],
        ),
    )

cursqlite.execute(
    """
    INSERT INTO curated_nuit (
        id_nuit, spo2_min, spo2_moy, spo2_mediane,
        nb_apnees, nb_hypopnees, nb_rera, nb_microeveils,
        dureehypoxiemin, position_dominante,
        decibels_max, decibels_moy, nbronflementsforts
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        id_nuit,
        spo2_min,
        spo2_moy,
        spo2_mediane,
        nb_apnees,
        nb_hypopnees,
        nb_rera,
        nb_microeveils,
        duree_hypoxie_min,
        position_dominante,
        decibels_max,
        decibels_moy,
        nbr_ronflements_forts,
    ),
)

cnx_sqlite.commit()
cnx_sqlite.close()

cur.close()
cnx.close()

print("3 PNG et 3 PDF générés avec succès.")
