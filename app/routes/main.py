# - Blueprint : Un outil pour organiser et regrouper les différentes routes de votre site en modules (comme des sous-dossiers).
# - render_template : Une fonction qui permet de générer et renvoyer une page web HTML finale au navigateur de l'utilisateur.
from flask import Blueprint, render_template

# Création du Blueprint "main" (le classeur qui regroupera les routes principales)
main_bp = Blueprint("main", __name__)


# Définition de la route pour l'URL racine (la page d'accueil "/")
@main_bp.route("/")
def index():
    # Va chercher le fichier "index.html" dans le dossier templates et le renvoie au client.
    # (Cela respecte le modèle MVC : on sépare la logique Python de l'affichage HTML)
    return render_template("index.html")