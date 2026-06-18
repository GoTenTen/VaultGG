# app/services/mistral_reco.py
"""Moteur de recommandation : une seule passe Mistral (mistral-small).

Bassin de reco = jeux non possédés (puisés dans la connaissance de Mistral,
tag "découverte") + jeux possédés mais peu joués (<60 min, tag "oubli", passés
EN ENTRÉE dans le prompt). Mistral propose des titres ; chacun est résolu en
app_id via IGDB (search_igdb_by_name), créé en base via _get_or_create_jeu, puis
persisté en Recommandation. Le tag n'est PAS stocké : il est dérivé à l'affichage.
"""
import json
from collections import Counter

import requests
from flask import current_app

from app.extensions import db
from app.models.utilisateurs import Bibliotheque, Jeu, Recommandation
from app.services.steam_library import _get_or_create_jeu
from app.services.igdb_enrichment import search_igdb_by_name

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
SEUIL_PEU_JOUE = 60      # minutes : en-dessous = "oubli" (acheté, jamais lancé)
MAX_PEU_JOUES = 30       # plafonne le prompt (tokens Mistral) sans tronquer la base


def _construire_profil(utilisateur):
    """Agrège le profil joueur à la volée depuis la Bibliotheque.

    On NE lit pas ProfilJoueur : ses champs sont dérivés et pas forcément à jour.
    Recalculer ici garde la reco cohérente avec l'état réel de la biblio.
    Bibliotheque n'a pas de relation ORM vers Jeu -> jointure explicite obligatoire.
    """
    entrees = (
        db.session.query(Bibliotheque, Jeu)
        .join(Jeu, Bibliotheque.jeu_id == Jeu.id)
        .filter(Bibliotheque.utilisateur_id == utilisateur.id)
        .all()
    )

    # (temps_de_jeu peut être None -> 'or 0' évite un TypeError dans la comparaison)
    joues = [(j, b.temps_de_jeu or 0) for b, j in entrees if (b.temps_de_jeu or 0) >= SEUIL_PEU_JOUE]
    peu_joues = [j for b, j in entrees if (b.temps_de_jeu or 0) < SEUIL_PEU_JOUE]

    joues.sort(key=lambda t: t[1], reverse=True)  # les + joués d'abord
    top_joues = joues[:12]

    # Genres dominants = genres les + fréquents PARMI les jeux réellement joués.
    # (Si non enrichis IGDB, genres = [] -> Counter vide, Mistral s'appuie sur les noms.)
    compteur = Counter()
    for jeu, _ in joues:
        for g in jeu.genres:
            compteur[g.libelle] += 1
    genres_dominants = [lib for lib, _ in compteur.most_common(5)]

    return genres_dominants, top_joues, peu_joues[:MAX_PEU_JOUES]


def _construire_prompt(genres, top_joues, peu_joues, n):
    """Assemble le message utilisateur. Format de sortie imposé = JSON strict."""
    profil = ", ".join(genres) if genres else "non déterminés"
    plus_joues = "; ".join(f"{j.nom} ({m // 60} h)" for j, m in top_joues) or "aucun"
    candidats_oubli = "; ".join(j.nom for j in peu_joues) or "aucun"

    return (
        f"Profil du joueur :\n"
        f"- Genres dominants : {profil}\n"
        f"- Jeux les plus joués : {plus_joues}\n"
        f"- Jeux possédés mais peu/pas joués : {candidats_oubli}\n\n"
        f"Propose {n} recommandations. Pour chacune, choisis un tag :\n"
        f'- "oubli" : UNIQUEMENT un jeu de la liste "peu/pas joués" qui mérite une 2e chance.\n'
        f'- "decouverte" : un jeu que le joueur ne possède PAS, cohérent avec ses goûts.\n'
        f"score = confiance entre 0 et 1. justification = 1 phrase, en français.\n"
        f'Réponds en JSON STRICT, sans texte autour : '
        f'{{"recommandations":[{{"nom":"...","tag":"oubli|decouverte","score":0.0,"justification":"..."}}]}}'
    )

# n => limite la réponse de mistral
def _appeler_mistral(prompt, n):
    cle = current_app.config["MISTRAL_API_KEY"]
    print("DEBUG clé Mistral:", repr(cle))  # DEBUG temporaire : None ou "" = .env pas lu
    """Appel HTTP unique à Mistral. response_format json_object force du JSON parsable."""
    resp = requests.post(
        MISTRAL_URL,
        headers={
            "Authorization": f"Bearer {current_app.config['MISTRAL_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": "mistral-small-latest",
            "temperature": 0.7,  # un peu de variété entre deux générations
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Tu es un expert en jeux vidéo qui recommande des titres."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    contenu = resp.json()["choices"][0]["message"]["content"]

    # Ceinture+bretelles : si jamais le modèle entoure de ```json malgré le format imposé.
    contenu = contenu.replace("```json", "").replace("```", "").strip()
    data = json.loads(contenu)
    return data.get("recommandations", [])[:n]


def generer_recommandations(utilisateur, n=8):
    """Orchestration complète. Renvoie le nb de recos effectivement persistées.

    Find-or-update par (user, jeu) : un re-run rafraîchit score/justification
    SANS écraser un feedback déjà saisi (la colonne feedback est conservée).
    """
    genres, top_joues, peu_joues = _construire_profil(utilisateur)
    prompt = _construire_prompt(genres, top_joues, peu_joues, n)
    recos = _appeler_mistral(prompt, n)

    nb = 0
    for r in recos:
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue

        infos = search_igdb_by_name(nom)  # {appid, name} ou None
        if infos is None:
            continue  # filtrage des non-matchs : pas de Jeu sans app_id Steam

        jeu = _get_or_create_jeu(infos)  # réutilisé tel quel : il lit ["appid"]/["name"]

        reco = Recommandation.query.filter_by(
            utilisateur_id=utilisateur.id, jeu_id=jeu.id
        ).first()
        if reco is None:
            reco = Recommandation(utilisateur_id=utilisateur.id, jeu_id=jeu.id, justification="")
            db.session.add(reco)

        reco.score_ia = r.get("score")
        reco.justification = (r.get("justification") or "")[:1000]  # colonne String(1000)
        nb += 1

    db.session.commit()  # 1 commit final = atomique (cohérent avec le reste du projet)
    return nb