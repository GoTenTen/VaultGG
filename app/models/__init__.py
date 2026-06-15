# On importe les modèles ici pour deux raisons :
# 1. Permettre "from app.models import Utilisateur" partout dans le projet.
# 2. SURTOUT : db.create_all() ne crée que les tables des modèles déjà
#    importés. Sans cette ligne, les tables de utilisateurs.py n'existerait jamais.
from app.models.utilisateurs import (
    Utilisateur, ProfilJoueur, Jeu, Genre,
    Avis, Backlog, Recommandation, Bibliotheque,
)