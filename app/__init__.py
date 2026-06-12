from flask import Flask
from config import Config
from app.extensions import db, login_manager

def create_app(config_class=Config):

    # Créationde l'objet app
    app = Flask(__name__)

    # Charge ce qui est présent dans Config (Keys) dans l'objet 'app'
    app.config.from_object(config_class)

    # Relie les extensions préalablement créées à notre application
    db.init_app(app)
    login_manager.init_app(app)

    # Import local pour éviter les imports circulaires, puis enregistrement des routes
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    # Fournit le contexte de l'application pour créer les tables manquantes
    with app.app_context():
        db.create_all()

    # Retourne l'application configurée et prête à fonctionner
    return app