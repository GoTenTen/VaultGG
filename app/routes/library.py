from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user
from config import Config
from app.services.steam_library import import_library
from app.services.igdb_enrichment import enrich_jeux

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

@library_bp.route("/enrich", methods=["POST"])
@login_required
def enrich():
    """Lance la passe d'enrichissement IGDB sur les Jeu non enrichis.

    Pattern PRG (Post/Redirect/Get) : on traite en POST puis on redirige,
    pour éviter le ré-enrichissement si l'utilisateur rafraîchit la page.

    Pas de filtrage par utilisateur : Jeu est partagé entre tous les users,
    enrichir un jeu profite à tous. La passe est globale, pas par compte.
    """
    ''' try:
        nb_enrichis, nb_sans_match = enrich_jeux()
    except Exception:
        # Flash générique : on n'expose pas l'erreur brute (token KO, IGDB
        # down, quota...) à l'utilisateur. Détail à logger en vrai en prod.
        flash("Erreur pendant l'enrichissement IGDB.", "danger")
        return redirect(url_for("main.index"))'''
    
    nb_enrichis, nb_sans_match = enrich_jeux()  # DEBUG : try/except retiré pour voir l'erreur brute

    if nb_enrichis == 0 and nb_sans_match == 0:
        # Aucun jeu à traiter : tout est déjà enrichi (ou biblio vide).
        flash("Aucun jeu à enrichir.", "info")
    else:
        # nb_sans_match = jeux absents d'IGDB : info utile, pas une erreur.
        flash(
            f"{nb_enrichis} jeu(x) enrichi(s), {nb_sans_match} sans correspondance IGDB.",
            "success",
        )
    return redirect(url_for("main.index"))