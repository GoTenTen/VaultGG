import requests
from app.extensions import db
from app.models.utilisateurs import Jeu, Bibliotheque

STEAM_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"


def fetch_owned_games(steam_id, api_key):
    """Appel réseau pur -> liste brute des jeux (ou [] si profil privé)."""
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": 1,             # -> renvoie le nom du jeu
        "include_played_free_games": 1,   # -> inclut les F2P joués
        "format": "json",
    }
    resp = requests.get(STEAM_OWNED_GAMES_URL, params=params, timeout=10)
    resp.raise_for_status()
    # Profil privé / 0 jeu -> {"response": {}} sans clé "games" : .get évite le KeyError
    return resp.json().get("response", {}).get("games", [])


def _get_or_create_jeu(game):
    """Find-or-create via app_id_steam (idempotence). flush (pas commit) -> obtient jeu.id."""
    app_id = game["appid"]
    jeu = Jeu.query.filter_by(app_id_steam=app_id).first()
    if jeu is None:
        jeu = Jeu(nom=game.get("name", f"App {app_id}"), app_id_steam=app_id)  # fallback si pas de nom
        db.session.add(jeu)
        db.session.flush()  # INSERT immédiat -> jeu.id dispo, transaction non close
    return jeu


def import_library(utilisateur, api_key):
    """Synchronise la biblio Steam en base. Idempotent (maj temps_de_jeu, pas de doublon)."""
    games = fetch_owned_games(utilisateur.steam_id, api_key)

    for game in games:
        jeu = _get_or_create_jeu(game)

        # Find-or-create de l'entrée pour le couple (user, jeu)
        entree = Bibliotheque.query.filter_by(
            utilisateur_id=utilisateur.id, jeu_id=jeu.id
        ).first()
        if entree is None:
            entree = Bibliotheque(utilisateur_id=utilisateur.id, jeu_id=jeu.id)
            db.session.add(entree)

        entree.temps_de_jeu = game.get("playtime_forever", 0)  # maj systématique (minutes)

    db.session.commit()  # 1 seul commit -> import atomique
    return len(games)