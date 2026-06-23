# Clinique_du_sommeil - Phase 2

# Objectif projet
- Lecture du CSV capteur
- Calcul les indicateurs cliniques
- Remplissage de la table resultat_nuit avec les indicateurs cliniques du csv et de la table evenement_respiratoire
- Envoi du CSV dans le datalake pour usage futur (modèle en étoile fait_nuits)
- Produire un rapport médical avec diagnostic et courbes que le médecin pourra charger plus tard

# Utilité du projet
Le projet va servir à connecter à une application front end(html/css/js) et back end(node.js/express.js) pour permettre au medecin de charger des rapport ainsi que des courbes sur des résultat d'analyse et ainsi implémenter les données nettoyées sur une IA disponible publiquement (TensorFlow)

# Préparation de l'environnement
Créer un fichier .env contenant :
   ````
    DB_HOST=localhost
    DB_USER=root
    DB_PASSWORD=votre_mdp
    DB_NAME=nom_base_donnees
    ```

Installer 
```
pip install dotenv
```

Installer 
```
pip install mysql-connector-python
```

Créer la base de données via le fichier SQL fourni ```cliniquenuitscompletes.sql```


# Génération des fichiers
Une fois la base de données SQL créée et la connexion établie, le script python peut être lancé.
Celui-ci générera automatiquement les fichiers et dossiers suivants :
- nuits/
    -{id_nuit}
        ├── rapport_medical_{id_nuit}.txt

        ├── spo2_{id_nuit}.png

        ├── spo2_{id_nuit}.pdf

        ├── debit_nasal_nuit_{id_nuit}.png

        ├── debit_nasal_nuit_{id_nuit}.pdf

        ├── ronflements_db_{id_nuit}.png

        └── ronflements_db_{id_nuit}.pdf

- raw/traite

- datalake.db