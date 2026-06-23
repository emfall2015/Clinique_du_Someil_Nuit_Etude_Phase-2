import pandas as pd
import mysql.connector
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
import csv
from pathlib import Path
import sqlite3



#-----------------------------------------------------
#-------- LECTURE FICHIER CSV-------------------------

# Pour choisir le csv a charger en fonction de l'id_nuit
id_nuit = input("Entrez l'id_nuit du fichier à charger : ")
id_medecin = input("Entrez l'id_medecin du fichier à charger : ")
commentaire = input("votre commentaire : ")

for fichier in os.listdir("./raw/"):
    if fichier.endswith(f"-{id_nuit}.csv"):
        df = pd.read_csv("./raw/"+fichier)
        break
else :
    print("Aucun fichier trouvé")

#-----------------------------------------------------
#-------- DUREE SOMMEIL MINUTES ----------------------

# ICI on crée une variable pour indiquer la durée du sommeil en fonction de la première et la dernière valeur de la colonne timestamp
#dure_sommeil_min = df['timestamp_sec'].max() - df['timestamp_sec'].min()/60

#---------------------------------------------------
df['timestamp_sec'] = pd.to_numeric(df['timestamp_sec'])

duree_sommeil_min = df['timestamp_sec'].max() - df['timestamp_sec'].min()/60

print(duree_sommeil_min)

#-----------------------------------------------------
#-------- LECTURE SQL---------------------------------

load_dotenv()

# connexion bdd clinique
cnx = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

print("Connexion réussie !")

#création d'une requête pour tester la connexion
cur = cnx.cursor()
query = "SELECT * FROM evenement_respiratoire where id_nuit = 1"

#éxecution de la requête
cur.execute(query)
result = cur.fetchall()


#-----------------------------------------------------
#-------- CALCUL INDICATEURS -------------------------

# Calcul des décibels max depuis le csv
decibels_max = df['ronflements_db'].max()

# Calcul de la moyenne des décibels depuis le csv
decibels_moy = round(df['ronflements_db'].mean(),1)

# Suppression d'éventuelles espaces sur les colonnes
df["timestamp_sec"] = df["timestamp_sec"].astype(str).str.strip()
df["spo2"] = df["spo2"].astype(str).str.strip()
df["debit_nasal_pct"] = df["debit_nasal_pct"].astype(str).str.strip()
df["effort_thoracique_pct"] = df["effort_thoracique_pct"].astype(str).str.strip()

df["position"] = df["position"].astype(str).str.strip()
df["ronflements_db"] = df["ronflements_db"].astype(str).str.strip()

df["flag_evenement"] = df["flag_evenement"].astype(str).str.strip()


df["spo2"] = pd.to_numeric(df["spo2"],errors="coerce")

# Calcul Min spo2
spo2_min = min(df["spo2"])

# Calcul Moyenne spo2
spo2_moy = round(df.loc[:,'spo2'].mean(),1)

# Calcul médiane spo2
spo2_mediane = round(df.loc[:,'spo2'].median(),1)


# Compter le nombre de secondes où spo2 < 90 - Chaque ligne 10 secondes 
duree_hypoxie = len(df.loc[df['spo2'] < 90]) * 10


# Calcul du nombre de ronflement fort 
df["ronflements_db"] = pd.to_numeric(df["ronflements_db"],errors="coerce")
nbr_ronflements_forts = len(df.loc[df["ronflements_db"]>70])


# Calcul de la position dominante

position_dominante = df['position'].value_counts()

# label de max value
position_dominante = position_dominante[position_dominante == max(position_dominante)].index.tolist()[0]


nb_doublons = df.duplicated().sum()



#-----------------------------------------------------
#-------- EXTRAPOLATION RESULTATS --------------------



# Copier le CSV brut dans /raw/traite/
df.to_csv(f"./raw/traite/traite_signal-psg-patient-2-nuit-{id_nuit}.csv", sep=",", index=False, encoding="utf-8-sig")

# # Charger les résultats_nuit dans SQL

cur.callproc('insert_data_night',(id_nuit,id_medecin, spo2_min, spo2_moy, spo2_mediane, duree_sommeil_min, duree_hypoxie, position_dominante, decibels_max, decibels_moy, nbr_ronflements_forts, commentaire))
cnx.commit()


#-----------------------------------------------------
#--------  Surlignage --------------- -------


temps_debut = None
intervalles_detectes = []

for index, row in df.iterrows():
        flag = row['flag_evenement']
        timestamp = row['timestamp_sec']
        # Gérer les cas où la valeur FLAG est manquante ou non numérique
        if pd.isna(flag):
            continue
            
        # Assurez-vous que le flag est bien un entier pour la comparaison
        try:
            flag_int = int(flag)
            timestamp_int = int(timestamp)
        except ValueError:
             # Si on ne peut pas convertir en entier, on ignore cette ligne
            continue

        if flag_int == 1:
            # Détection du début (Transition 0 -> 1 ou 1 -> 1)
            # On enregistre le temps si nous n'en avons pas encore.
            if temps_debut is None:
                temps_debut = timestamp_int/10
               
        elif flag_int == 0:
            # Détection de la fin (Transition 1 -> 0)
            if temps_debut is not None:
                temps_fin = (timestamp_int - 10)/10
                intervalle = (temps_debut, temps_fin)
                intervalles_detectes.append(intervalle)
                                
                # Réinitialiser l'état
                temps_debut = None 
            else:
                # On trouve un '0', mais le début était soit absent, soit déjà traité.
                pass

print(intervalles_detectes)


#-----------------------------------------------------
#-------- COURBES ------------------------------------

# Dossier de destination
dossier = Path(f"nuits/{id_nuit}")

# Création du dossier et des sous-dossiers si nécessaire
dossier.mkdir(parents=True, exist_ok=True)

# Générer une courbe PNG et PDF pour debit nasal
# Objectif : visualiser les données.
debit = []
ronflement_db = []
spo2 = []
with open("./raw/"+fichier, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=',')
    for row in reader:
        debit.append(float(row["debit_nasal_pct"]))
        ronflement_db.append(float(row["ronflements_db"]))
        spo2.append(float(row["spo2"]))


heures = list(range(len(debit)))

fig,ax = plt.subplots()
for i in intervalles_detectes:
    ax.axvspan(i[0],i[1], facecolor ='green', alpha = 0.5)
plt.plot(heures, debit, marker='')
plt.xlabel("/10 secondes")
plt.ylabel("Débit nasal")
plt.title("Évolution du débit nasal sur une heure par tranche de 10 secondes")
plt.grid(True)
plt.savefig(dossier / f"debit_nasal_nuit_{id_nuit}.png")
plt.savefig(dossier / f"debit_nasal_nuit_{id_nuit}.pdf")
plt.close()

fig,ax2 = plt.subplots()
for i in intervalles_detectes:
    ax2.axvspan(i[0],i[1], facecolor ='green', alpha = 0.5)
plt.plot(heures, ronflement_db, marker='')
plt.xlabel("/10 secondes")
plt.ylabel("Ronflement (dB)")
plt.title("Évolution du ronflement sur une heure par tranche de 10 secondes")
plt.grid(True)
plt.savefig(dossier / f"ronflement_db_{id_nuit}.png")
plt.savefig(dossier / f"ronflement_db_{id_nuit}.pdf")
plt.close()

fig,ax3 = plt.subplots()
for i in intervalles_detectes:
    ax3.axvspan(i[0],i[1], facecolor ='green', alpha = 0.5)
plt.plot(heures, spo2, marker='')
plt.xlabel("/10 secondes")
plt.ylabel("spo2")
plt.title("Évolution du spo2 sur une heure par tranche de 10 secondes")
plt.grid(True)
plt.savefig(dossier / f"spo2_{id_nuit}.png")
plt.savefig(dossier / f"spo2_{id_nuit}.pdf")
plt.close()


#-----------------------------------------------------
#-------- Rapport Medical ----------------------------

cur = cnx.cursor()

requete = """
SELECT nb_apnees, nb_hypopnees, nb_rera,iah,nb_microeveils,duree_hypoxie_min
FROM resultat_nuit
WHERE id_nuit = %s
"""

cur.execute(requete, (id_nuit,))
result = cur.fetchone()

if result:
    nb_apnees = result[0]
    nb_hypopnees = result[1]
    nb_rera = result[2]
    iah = result[3]
    nb_microeveils = result[4]
    duree_hypoxie_min = result[5]
else:
    nb_apnees = 0
    nb_hypopnees = 0
    nb_rera = 0
    iah = 0
    nb_microeveils=0
    duree_hypoxie_min=0


with open(dossier / f"rapport_medical_{id_nuit}.txt", "w", encoding="utf-8") as f:
    f.write("=== Rapport médical pour le Medecin ===\n\n")
    
    f.write("============================================\n")
    f.write(f"=== Nuit : {id_nuit} ===\n\n")
    f.write(f"=== Medecin : {id_medecin} ===\n\n")
    f.write("Spo2 min/moy/max: \n\n")
    f.write(f"minimum :{spo2_min}\n\n")
    f.write(f"moyen :{spo2_moy}\n\n")
    f.write(f"mediane :{spo2_mediane}\n\n")
    f.write("============================================\n\n")
    f.write("Ronflement fort (>70dB): \n\n")
    f.write(f"{nbr_ronflements_forts}\n\n")
    f.write("intensité des ronflements : \n\n")
    f.write(f" MAX : {decibels_max} \n\n")
    f.write(f" MOYEN : {decibels_moy}\n\n")
    f.write("============================================\n\n")
    f.write("Duree Hypoxie : \n\n")
    f.write(f"{duree_hypoxie} min\n\n")
    f.write("============================================\n\n")
    f.write("Position Dominante : \n\n")
    f.write(f" {position_dominante}\n\n")
    f.write("============================================\n\n")
    f.write("Nombre d’apnées / hypopnées / RERA : \n\n")
    f.write(f" apnées :{nb_apnees}\n\n")
    f.write(f" hypopnées :{nb_hypopnees}\n\n")
    f.write(f" RERA :{nb_rera}\n\n")
    f.write("============================================\n\n")
    f.write("IAH : \n\n")
    f.write(f" IAH:{iah}\n\n")
    f.write("Commentaire du medecin : \n\n")
    f.write(f"  {commentaire}\n\n")
    print(f"Rapport Medical généré dans 'rapport_medical.txt'.")


#-----------------------------------------------------
#--------  Création du datalake --------------- --------------------
cnx_sqlite = sqlite3.connect("datalake.db")
cursqlite = cnx_sqlite.cursor()
cursqlite.execute("CREATE TABLE IF NOT EXISTS raw_capteur (id_raw INTEGER PRIMARY KEY AUTOINCREMENT,id_nuit  INTEGER NOT NULL,timestamp_sec INTEGER NOT NULL,spo2 REAL,debitnasalpct REAL,effortthoraciquepct REAL,position TEXT,ronflements_db REAL,flagevenement INTEGER CHECK (flagevenement IN (0,1)))")
cursqlite.execute("CREATE TABLE IF NOT EXISTS curated_nuit (id_curated INTEGER PRIMARY KEY AUTOINCREMENT,id_nuit INTEGER NOT NULL,spo2_min REAL,spo2_moy REAL,spo2_mediane REAL,nb_apnees INTEGER,nb_hypopnees INTEGER,nb_rera INTEGER,nb_microeveils INTEGER,dureehypoxiemin REAL,position_dominante TEXT,decibels_max REAL,decibels_moy REAL,nbronflementsforts INTEGER)")
for _, row in df.iterrows():
    cursqlite.execute(
        """
        INSERT INTO raw_capteur (
            id_nuit,
            timestamp_sec,
            spo2,
            debitnasalpct,
            effortthoraciquepct,
            position,
            ronflements_db,
            flagevenement
        )
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            id_nuit,
            row["timestamp_sec"],
            row["spo2"],
            row["debit_nasal_pct"],
            row["effort_thoracique_pct"],
            row["position"],
            row["ronflements_db"],
            row["flag_evenement"]
        )
    )


cursqlite.execute("""
    INSERT INTO curated_nuit (
        id_nuit,
        spo2_min,
        spo2_moy,
        spo2_mediane,
        nb_apnees,
        nb_hypopnees,
        nb_rera,
        nb_microeveils,
        dureehypoxiemin,
        position_dominante,
        decibels_max,
        decibels_moy,
        nbronflementsforts
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
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
    nbr_ronflements_forts
))


cnx_sqlite.commit()




