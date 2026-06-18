from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.utilisateurs import Recommandation, Jeu
from app.services.mistral_reco import generer_recommandations

recommandation_bp = Blueprint("recommandation", __name__)


@recommandation_bp.route("/recommandations")
@login_required
def liste():
    """Affiche les recos du user. Le tag découverte/oubli est DÉRIVÉ ici."""
    lignes = (
        db.session.query(Recommandation, Jeu)
        .join(Jeu, Recommandation.jeu_id == Jeu.id)
        .filter(Recommandation.utilisateur_id == current_user.id)
        # On trie d'abord les None, puis par score décroissant.
        .order_by(Recommandation.score_ia.is_(None), Recommandation.score_ia.desc())
        .all()
    )

    # "oubli" = possédé MAIS peu joué (<60 min). Possédé-et-déjà-joué n'est pas un oubli.
    SEUIL = 60
    peu_joues = {
        b.jeu_id for b in current_user.bibliotheque
        if (b.temps_de_jeu or 0) < SEUIL
    }
    items = [
        {"reco": r, "jeu": j, "tag": "oubli" if j.id in peu_joues else "decouverte"}
        for r, j in lignes
    ]
    return render_template("recommandations.html", items=items)


@recommandation_bp.route("/recommandations/generer", methods=["POST"])
@login_required
def generer():
    """PRG : génère puis redirige (pas de re-génération au refresh)."""
    try:
        nb = generer_recommandations(current_user)
    except Exception:
        # Générique : on n'expose ni la clé Mistral ni l'erreur brute à l'user.
        flash("Échec de la génération des recommandations.", "danger")
        return redirect(url_for("recommandation.liste"))

    if nb == 0:
        flash("Aucune recommandation (biblio vide ou aucun match IGDB).", "warning")
    else:
        flash(f"{nb} recommandation(s) générée(s).", "success")
    return redirect(url_for("recommandation.liste"))