from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user
from config import Config
from app.services.steam_library import import_library

# Blueprint dédié à la bibliothèque -> garde auth.py centré sur l'authentification
library_bp = Blueprint("library", __name__)


@library_bp.route("/import", methods=["POST"])
@login_required  # PIÈGE : besoin de current_user.steam_id -> route inaccessible sans session
def import_steam():
    """Déclenche l'import de la biblio Steam de l'utilisateur connecté."""
    try:
        nb = import_library(current_user, Config.STEAM_API_KEY)
        # nb == 0 est ambigu : profil privé OU vraiment 0 jeu (Steam ne les distingue pas)
        if nb == 0:
            flash("Aucun jeu importé (profil Steam privé ?).", "warning")
        else:
            flash(f"{nb} jeux importés depuis Steam.", "success")
    except Exception:
        # On n'expose pas l'erreur brute (clé API, URL) à l'user -> message générique
        flash("Échec de l'import Steam, réessaie plus tard.", "danger")

    # POST -> redirect (pattern PRG) : évite le ré-import si l'user rafraîchit la page
    return redirect(url_for("main.index"))