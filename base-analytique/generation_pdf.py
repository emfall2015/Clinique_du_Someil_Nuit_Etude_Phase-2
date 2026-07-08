
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image 
from reportlab.lib.styles import getSampleStyleSheet
from pathlib import Path


def generer_pdf_patient(patient, detail, rapport, comorbidite, probabilite, nuit_dir):
    
    # Dossier du projet (parent de base-analytique)
    racine_projet = Path(__file__).resolve().parent.parent
    
    id_patient = patient['id_patient']
    id_nuit = patient['id_nuit']

    dossier_patient = racine_projet / "patients" / str(id_patient)
    dossier_nuit = dossier_patient / f"nuit{id_nuit}"

    dossier_nuit.mkdir(parents=True, exist_ok=True)

    fichier = dossier_nuit / "rapport_médical.pdf"
    


    doc = SimpleDocTemplate(str(fichier))

    styles = getSampleStyleSheet()

    contenu = []


    # TITRE
    contenu.append(
        Paragraph(
            "Rapport Patient - Clinique du Sommeil d'Arles",
            styles["Title"]
        )
    )

    contenu.append(Spacer(1, 20))


    # INFOS PATIENT
    contenu.append(
        Paragraph(
            f"""
            <b>Patient :</b> {patient['nom']} {patient['prenom']}<br/>
            <b>ID Patient :</b> {patient['id_patient']}<br/>
            <b>Date de la nuit :</b> {patient['date_nuit']}<br/>
            <b>IAH :</b> {patient['iah']}<br/>
            <b>Sévérité :</b> {patient['severite_iah']}
            """,
            styles["Normal"]
        )
    )


    contenu.append(Spacer(1,20))


    # RESULTATS DETAIL
    contenu.append(
        Paragraph(
            "Résultats détaillés de la nuit",
            styles["Heading2"]
        )
    )


    for colonne in detail.columns:

        contenu.append(
            Paragraph(
                f"{colonne} : {detail[colonne].iloc[0]}",
                styles["Normal"]
            )
        )


    contenu.append(Spacer(1,20))


    # IA
    contenu.append(
        Paragraph(
            "Analyse IA - Comorbidités",
            styles["Heading2"]
        )
    )


    contenu.append(
        Paragraph(
            f"""
            Diagnostic probable : {comorbidite}<br/>
            Probabilité : {probabilite*100:.1f} %
            """,
            styles["Normal"]
        )
    )


    contenu.append(Spacer(1,20))


    # RAPPORT MEDICAL
    contenu.append(
        Paragraph(
            "Rapport médical complet",
            styles["Heading2"]
        )
    )


    contenu.append(
        Paragraph(
            rapport.replace("\n","<br/>"),
            styles["Normal"]
        )
    )


    # GRAPHIQUES
    contenu.append(
        Paragraph(
            "Courbes de la nuit",
            styles["Heading2"]
        )
    )

    id_nuit = patient['id_nuit']

    for img in [
        f"spo2_{id_nuit}.png",
        f"debit_nasal_nuit_{id_nuit}.png",
        f"ronflement_db_{id_nuit}.png"
    ]:

        chemin = nuit_dir / img
       
        if chemin.exists():
            print("Ajout image dans PDF :", chemin)
            contenu.append(
                Image(
                    str(chemin),
                    width=600,
                    height=400
                )
            )

            contenu.append(Spacer(1,20))


    doc.build(contenu)


    return str(fichier)