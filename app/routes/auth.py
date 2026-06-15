# app/routes/auth.py
from flask import Blueprint, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required

from app.extensions import db
from app.models import Utilisateur  # adapte si ton import diffère
from app.services.steam_auth import build_login_url, verify_response, fetch_steam_profile

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    # _external=True → URL absolue (http://host/...), requise car Steam doit
    # renvoyer vers une adresse complète. realm = racine du domaine.
    return_to = url_for("auth.callback", _external=True)
    realm = request.host_url.rstrip("/")
    return redirect(build_login_url(return_to, realm))


@auth_bp.route("/callback")
def callback():
    steamid = verify_response(request.args)
    if not steamid:  # vérification échouée → on ne connecte personne
        flash("Échec de la connexion Steam.", "danger")
        return redirect(url_for("main.index"))

    # find-or-create : user existant, sinon création depuis le profil Steam.
    user = Utilisateur.query.filter_by(steam_id=steamid).first()
    if user is None:
        profile = fetch_steam_profile(steamid)
        user = Utilisateur(
            steam_id=steamid,
            pseudo=profile.get("personaname", f"Joueur_{steamid[-4:]}"),  # fallback si vide
            avatar_url=profile.get("avatarfull"),
            # email reste NULL : Steam ne le fournit pas → doit être nullable.
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)  # session Flask-Login (cookie signé)
    return redirect(url_for("main.index"))


@auth_bp.route("/logout")
@login_required  # rien à déconnecter si pas connecté
def logout():
    logout_user()
    return redirect(url_for("main.index"))