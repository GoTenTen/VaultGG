# app/services/igdb_auth.py
"""Gestion du token OAuth Twitch nécessaire pour appeler IGDB.

Pourquoi un fichier séparé : l'auth est une responsabilité distincte de
l'enrichissement. Le token Twitch est partagé par tous les appels IGDB et
sa logique de cache n'a rien à voir avec le mapping jeu -> métadonnées.
"""
import time
import requests

# Cache module-level : le token Twitch vit ~60 jours, on évite de le
# régénérer à chaque appel IGDB. Stocké en mémoire process (suffisant pour
# une app desktop mono-utilisateur ; pas de partage entre process).
_token_cache = {"access_token": None, "expires_at": 0}


def get_igdb_token(client_id, client_secret):
    """Renvoie un token valide, en le régénérant seulement si expiré.

    Piège : Twitch renvoie 'expires_in' (durée en secondes), pas une date.
    On convertit en timestamp absolu, et on retranche 60s de marge pour
    éviter d'utiliser un token qui expire pile pendant la requête.
    """
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",  # flow sans utilisateur
        },
        timeout=10,
    )
    resp.raise_for_status()  # remonte une erreur claire si credentials KO
    data = resp.json()

    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data["expires_in"] - 60
    return _token_cache["access_token"]