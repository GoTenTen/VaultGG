# app/services/igdb_enrichment.py
"""Enrichissement des Jeu via IGDB, en passe séparée (après l'import Steam).

Matching par app_id_steam, en BATCH : une requête couvre jusqu'à 100 jeux,
au lieu d'une requête par jeu. Passe une biblio de 80+ jeux de ~30s à ~1s.
"""
import requests
from flask import current_app

from app.extensions import db
from app.models.utilisateurs import Jeu, Genre
from app.services.igdb_auth import get_igdb_token

IGDB_URL = "https://api.igdb.com/v4/games"
STEAM_SOURCE = 1   # id de Steam dans /external_game_sources (vérifié)
BATCH_SIZE = 100   # IGDB plafonne à 500 résultats ; 100 garde de la marge


def _query_igdb_batch(steam_ids, client_id, token):
    """Interroge IGDB pour une LISTE de Steam IDs en une seule requête.

    Renvoie un dict {steam_id (str): data_du_jeu} pour redistribution.

    Piège : on filtre external_games.uid = (...) au niveau du JEU, mais IGDB
    renvoie alors TOUS les external_games du jeu (Amazon, GOG, etc.), pas que
    Steam. Il faut donc, côté Python, retrouver le sous-objet Steam pour lire
    le bon uid -> d'où la boucle interne sur external_games.
    """
    # APIcalypse veut une liste entre parenthèses : ("730","4000",...).
    ids_str = ",".join(f'"{sid}"' for sid in steam_ids)
    body = (
        f'fields name, total_rating, genres.name, '
        f'external_games.external_game_source, external_games.uid; '
        f'where external_games.external_game_source = {STEAM_SOURCE} '
        f'& external_games.uid = ({ids_str}); '
        f'limit {len(steam_ids)};'  # sinon IGDB tronque à 10 par défaut
    )
    resp = requests.post(
        IGDB_URL,
        headers={"Client-ID": client_id, "Authorization": f"Bearer {token}"},
        data=body,
        timeout=15,
    )
    resp.raise_for_status()

    # Redistribution : pour chaque jeu renvoyé, on retrouve SON uid Steam
    # (le seul external_game dont la source = Steam) et on l'indexe dessus.
    par_steam_id = {}
    for jeu_data in resp.json():
        for ext in jeu_data.get("external_games", []):
            if ext.get("external_game_source") == STEAM_SOURCE:
                par_steam_id[ext["uid"]] = jeu_data
                break  # un seul lien Steam par jeu, inutile de continuer
    return par_steam_id


def _get_or_create_genre(libelle):
    """Find-or-create d'un Genre par libellé (attribut unique en base).

    Idempotent : un genre revient sur des centaines de jeux, pas de doublon.
    flush() pour l'id sans committer (commit global géré par l'appelant).
    """
    genre = Genre.query.filter_by(libelle=libelle).first()
    if genre is None:
        genre = Genre(libelle=libelle)
        db.session.add(genre)
        db.session.flush()
    return genre


def _apply_metadata(jeu, data):
    """Écrit les métadonnées IGDB sur un Jeu.

    total_rating (0-100) peut être absent si trop peu de votes -> None gardé
    plutôt qu'un 0 trompeur. genres remplacés (pas ajoutés) pour refléter
    l'état IGDB courant en cas de ré-enrichissement.
    """
    jeu.note_igbd = data.get("total_rating")
    jeu.genres = [
        _get_or_create_genre(g["name"])
        for g in data.get("genres", [])
    ]


def enrich_jeux():
    """Enrichit en batch les Jeu non encore enrichis (note_igbd IS NULL).

    Renvoie (nb_enrichis, nb_sans_match). Critère NULL = passe rejouable.

    Note évolutivité : si la biblio dépasse 500 jeux non enrichis, le
    découpage en lots BATCH_SIZE gère déjà ça (plusieurs requêtes). Au-delà
    de ~4 lots/seconde il faudrait throttler (quota IGDB), non atteint ici.
    """
    client_id = current_app.config["TWITCH_CLIENT_ID"]
    client_secret = current_app.config["TWITCH_CLIENT_SECRET"]
    token = get_igdb_token(client_id, client_secret)

    a_enrichir = Jeu.query.filter(Jeu.note_igbd.is_(None)).all()
    nb_enrichis = 0
    nb_sans_match = 0

    # Découpage en lots : on parcourt la liste par tranches de BATCH_SIZE.
    for i in range(0, len(a_enrichir), BATCH_SIZE):
        lot = a_enrichir[i:i + BATCH_SIZE]
        # IGDB matche sur des uid string -> on convertit l'app_id (int) en str.
        steam_ids = [str(jeu.app_id_steam) for jeu in lot]
        resultats = _query_igdb_batch(steam_ids, client_id, token)

        for jeu in lot:
            data = resultats.get(str(jeu.app_id_steam))
            if data is None:
                nb_sans_match += 1  # jeu absent d'IGDB (ou pas de lien Steam)
                continue
            _apply_metadata(jeu, data)
            nb_enrichis += 1

    db.session.commit()  # un seul commit en fin de passe = atomique
    return nb_enrichis, nb_sans_match