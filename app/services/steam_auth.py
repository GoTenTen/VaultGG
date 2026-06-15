# app/services/steam_auth.py
import re
import requests
from flask import current_app
from urllib.parse import urlencode

# Steam n'a qu'un endpoint OpenID, sans secret : la sécurité repose
# entièrement sur la re-vérification (verify_response).
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

# Extrait le steamid64 (17 chiffres) noyé dans l'URL renvoyée par Steam :
# https://steamcommunity.com/openid/id/76561198012345678
# Le `$` ancre la fin pour ne capturer que l'ID terminal.
STEAM_ID_RE = re.compile(r"steamcommunity\.com/openid/id/(\d+)$")


def build_login_url(return_to: str, realm: str) -> str:
    # Assemble l'URL de redirection vers Steam (aucun appel réseau ici).
    # return_to : notre /callback absolu. realm : doit englober return_to,
    # sinon Steam rejette.
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",  # version protocole, fixe
        "openid.mode": "checkid_setup",                    # affiche l'écran de login
        # identifier_select = identité encore inconnue, c'est l'user qui la révèle
        # en se loggant → c'est ce réglage qui déclenche la page Steam.
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.return_to": return_to,
        "openid.realm": realm,
    }
    # urlencode échappe les `:` et `/` des URLs imbriquées (sinon casse).
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


def verify_response(query_params: dict) -> str | None:
    # PIÈGE SÉCURITÉ : /callback est public, on ne fait JAMAIS confiance au
    # claimed_id brut (forgeable). On renvoie les params à Steam en mode
    # check_authentication : lui seul connaît sa signature → is_valid:true.
    # Retourne le steamid64 si validé, sinon None.
    payload = {k: v for k, v in query_params.items() if k.startswith("openid.")}
    # Seul changement autorisé : le mode. Modifier un autre param invaliderait
    # la signature qui porte sur l'ensemble.
    payload["openid.mode"] = "check_authentication"

    # Appel réseau serveur-à-serveur. timeout pour ne pas bloquer si Steam tarde.
    resp = requests.post(STEAM_OPENID_URL, data=payload, timeout=10)

    # Réponse en texte brut, pas JSON. Pas de is_valid:true = forgé/expiré.
    if "is_valid:true" not in resp.text:
        return None

    claimed_id = query_params.get("openid.claimed_id", "")
    match = STEAM_ID_RE.search(claimed_id)
    return match.group(1) if match else None  # None si format inattendu, par sécurité


def fetch_steam_profile(steamid: str) -> dict:
    # Séparé de verify_response : authentifier (qui es-tu) ≠ enrichir le profil
    # (pseudo, avatar). Permet aussi de rafraîchir un profil sans re-auth.
    resp = requests.get(
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
        params={"key": current_app.config["STEAM_API_KEY"], "steamids": steamid},
        timeout=10,
    )
    # Structure : {"response": {"players": [{...}]}}. .get en cascade = pas de KeyError.
    players = resp.json().get("response", {}).get("players", [])
    return players[0] if players else {}  # {} si introuvable, au caller de gérer