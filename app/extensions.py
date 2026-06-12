# Ici sera le fichier pour tout ce qui touche à Flask

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Initialise l'outil de gestion de la base de données
db = SQLAlchemy()

# Initialise l'outil de gestion des sessions (connexion/déconnexion)
login_manager = LoginManager()

# Indique la page vers laquelle rediriger un utilisateur non connecté
login_manager.login_view = "main.index"

