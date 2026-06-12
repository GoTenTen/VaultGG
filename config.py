import os
from dotenv import load_dotenv

# load_dotenv lit le fichier .env et injecte son contenu dans les "variables" plus bas
load_dotenv()

# Chemin absolu du dossier où se trouve CE fichier (la racine du projet).
# __file__ = le chemin de config.py ; dirname = son dossier ; abspath = version absolue. 
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-a-changer-en-prod") # => cookies session flask

    # URL de connexion à la base de données (SQLite par défaut)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "vaultgg.db")
    )

    # Désactive un mécanisme de suivi de SQLAlchemy, coûteux et inutile ici.
    SQLALCHEMY_TRACK_MODIFICATIONS = False