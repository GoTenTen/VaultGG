# app/services/hltb_enrichment.py
"""Enrichissement de la durée des Jeu via HowLongToBeat (passe séparée).

HLTB n'a pas d'API officielle : la lib howlongtobeatpy scrape le site et
matche PAR NOM. Conséquences assumées :
    - faillible : matching nominal -> garde-fou par seuil de similarité.
    - lent : ~3-5s/jeu (la lib enchaîne plusieurs requêtes : page, script,
    token, recherche). Pas de batch possible. Le spinner front couvre l'attente.
"""
from fake_useragent import UserAgent

# --- Monkey-patch CRITIQUE, à exécuter AVANT d'importer howlongtobeatpy ---
# La lib tire un User-Agent au hasard via fake_useragent. HLTB rejette les UA
# exotiques/anciens (erreur "IFW-U01" -> connexion suspendue/403). On force un
# UA Chrome desktop récent fixe pour des requêtes fiables. Patch en mémoire :
# ne modifie pas le code de la lib (survit aux réinstallations).
_UA_FIXE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
UserAgent.random = property(lambda self: _UA_FIXE)

# Import APRÈS le patch : sinon la lib aurait déjà capturé l'ancien comportement.
from howlongtobeatpy import HowLongToBeat  # noqa: E402 (import volontairement non en tête)

from app.extensions import db
from app.models.utilisateurs import Jeu

# Seuil de confiance sur le matching nominal. La lib filtre déjà à 0.4 ;
# on remonte à 0.5 pour écarter les rapprochements douteux (une mauvaise
# durée est pire qu'une absence de durée).
SEUIL_SIMILARITE = 0.5


def _chercher_duree(nom_jeu, hltb):
    """Cherche la durée 'main story' d'un jeu par son nom sur HLTB.

    Renvoie un float (heures) ou None. None couvre 3 cas indistincts :
    aucun résultat, meilleur match sous le seuil, ou jeu sans main_story
    (ex. multijoueur pur comme CS2 -> pas d'"histoire à finir").
    """
    resultats = hltb.search(nom_jeu)
    if not resultats:  # None (erreur) ou liste vide (aucun match)
        return None

    meilleur = max(resultats, key=lambda e: e.similarity)
    if meilleur.similarity < SEUIL_SIMILARITE:
        return None  # match trop incertain : on préfère ne rien écrire

    # main_story = durée moyenne pour finir l'histoire principale, en heures.
    # Vaut 0 si HLTB n'a pas la donnée -> on traite 0 comme absent (None).
    return meilleur.main_story or None


def enrich_durees():
    """Parcourt les Jeu sans durée (duree_hltb IS NULL) et la complète.

    Renvoie (nb_enrichis, nb_sans_match). Critère NULL = passe rejouable :
    on ne re-scrape pas un jeu déjà traité.

    Lenteur assumée (~3-5s/jeu). Évolution possible : async_search (fourni par
    la lib) pour paralléliser, au risque d'un rate-limit côté HLTB.
    """
    hltb = HowLongToBeat(SEUIL_SIMILARITE)  # instancié une fois, réutilisé
    a_enrichir = Jeu.query.filter(Jeu.duree_hltb.is_(None)).all()
    nb_enrichis = 0
    nb_sans_match = 0

    for jeu in a_enrichir:
        print(f"[HLTB] {jeu.nom}", flush=True)  # DEBUG progression ; flush pour affichage immédiat
        duree = _chercher_duree(jeu.nom, hltb)
        if duree is None:
            nb_sans_match += 1
            continue
        jeu.duree_hltb = duree
        nb_enrichis += 1

    db.session.commit()  # un seul commit en fin de passe
    return nb_enrichis, nb_sans_match