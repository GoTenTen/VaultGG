from flask_login import UserMixin
from app.extensions import db


# Table d'association n-n SANS attribut propre -> simple db.Table, pas une classe.
# (Si la relation portait une donnée, il faudrait une vraie classe : voir Bibliotheque.)
jeu_genre = db.Table(
    "jeu_genre",
    db.Column("jeu_id", db.ForeignKey("jeu.id"), primary_key=True),
    db.Column("genre_id", db.ForeignKey("genre.id"), primary_key=True),
)


# db.Model -> devient une table SQL. UserMixin -> fournit les 4 méthodes
# exigées par Flask-Login (is_authenticated, is_active, is_anonymous, get_id).
class Utilisateur(db.Model, UserMixin):
    __tablename__ = "utilisateur"

    id = db.Column(db.Integer, primary_key=True)

    # SteamID64 (17 chiffres) -> String, car il dépasse l'entier SQL 32 bits.
    steam_id = db.Column(db.String(20), unique=True, nullable=False)
    pseudo = db.Column(db.String(100), nullable=True)       # rafraîchi à chaque connexion Steam
    avatar_url = db.Column(db.String(255), nullable=True)
    # joueur/admin par ATTRIBUT, pas héritage. Promotion admin à la main.
    role = db.Column(db.String(20), nullable=False, default="joueur")
    # func.now() SANS appel final : la base l'exécute à chaque insert (sinon date figée au démarrage).
    date_creation = db.Column(db.DateTime, server_default=db.func.now())

    # uselist=False -> 1-1 ; delete-orphan -> le profil meurt avec l'user (composition).
    profil = db.relationship("ProfilJoueur", backref="utilisateur",uselist=False, cascade="all, delete-orphan")
    # 1-n : la bibliothèque possédée part avec l'user si supprimé.
    bibliotheque = db.relationship("Bibliotheque", backref="utilisateur",cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Utilisateur {self.id} - {self.pseudo}>"


# Composition 1-1 avec Utilisateur. Les 3 champs sont DÉRIVÉS
# (agrégés depuis la biblio + les avis), remplis plus tard par un mettre_a_jour().
class ProfilJoueur(db.Model):
    __tablename__ = "profil_joueur"

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.ForeignKey("utilisateur.id"), unique=True, nullable=False)  # unique -> 1 profil/user
    genre_dominant = db.Column(db.String(50), nullable=True)
    heures_totales = db.Column(db.Integer, nullable=True)
    style_jeu = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"<ProfilJoueur user={self.utilisateur_id}>"


class Jeu(db.Model):
    __tablename__ = "jeu"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    # app_id Steam : clé d'idempotence à l'import (évite de réinsérer un jeu déjà en base).
    app_id_steam = db.Column(db.Integer, unique=True, nullable=False)
    duree_hltb = db.Column(db.Float, nullable=True)   # HowLongToBeat, en heures
    note_igbd = db.Column(db.Float, nullable=True)    # IGDB (étape 7), nullable tant que pas enrichi
    genres = db.relationship("Genre", secondary=jeu_genre, backref="jeux")

    def __repr__(self):
        return f"<Jeu {self.id} - {self.nom}>"


class Genre(db.Model):
    __tablename__ = "genre"

    id = db.Column(db.Integer, primary_key=True)
    libelle = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Genre {self.libelle}>"


# --- Classes-associations : portent un attribut métier -> vraie classe (pas db.Table) ---

class Avis(db.Model):
    __tablename__ = "avis"

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.ForeignKey("utilisateur.id"), nullable=False)
    jeu_id = db.Column(db.ForeignKey("jeu.id"), nullable=False)
    note = db.Column(db.Integer, nullable=False)         # plage validée côté route, pas en base
    commentaire = db.Column(db.String(1000), nullable=True)
    date_avis = db.Column(db.Date, nullable=True)        # db.Date : l'heure n'a pas de sens ici
    __table_args__ = (db.UniqueConstraint("utilisateur_id", "jeu_id"),)  # 1 avis / jeu / user

    def __repr__(self):
        return f"<Avis user={self.utilisateur_id} jeu={self.jeu_id} note={self.note}>"


class Backlog(db.Model):
    __tablename__ = "backlog"

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.ForeignKey("utilisateur.id"), nullable=False)
    jeu_id = db.Column(db.ForeignKey("jeu.id"), nullable=False)
    statut = db.Column(db.String(20), nullable=False, default="a_jouer")
    priorite = db.Column(db.Integer, nullable=True)
    date_ajout = db.Column(db.Date, nullable=True)
    __table_args__ = (db.UniqueConstraint("utilisateur_id", "jeu_id"),)  # un jeu pas 2x dans le backlog

    def __repr__(self):
        return f"<Backlog user={self.utilisateur_id} jeu={self.jeu_id} statut={self.statut}>"


class Recommandation(db.Model):
    __tablename__ = "recommandation"

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.ForeignKey("utilisateur.id"), nullable=False)
    jeu_id = db.Column(db.ForeignKey("jeu.id"), nullable=False)
    score_ia = db.Column(db.Float, nullable=True)            # confiance renvoyée par Mistral
    justification = db.Column(db.String(1000), nullable=False)
    feedback = db.Column(db.String(1000), nullable=True)     # rempli après coup ("Donner un feedback", extend)

    def __repr__(self):
        return f"<Recommandation user={self.utilisateur_id} jeu={self.jeu_id}>"


# Classe-association Utilisateur <-> Jeu portant temps_de_jeu.
# C'est la source de get_bibliotheque() et de heures_totales (= SUM(temps_de_jeu)).
class Bibliotheque(db.Model):
    __tablename__ = "bibliotheque"

    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.ForeignKey("utilisateur.id"), nullable=False)
    jeu_id = db.Column(db.ForeignKey("jeu.id"), nullable=False)
    temps_de_jeu = db.Column(db.Integer, default=0)  # minutes (Steam = playtime_forever en minutes), pas de conversion à l'import
    __table_args__ = (db.UniqueConstraint("utilisateur_id", "jeu_id"),)  # idempotence du ré-import Steam

    def __repr__(self):
        return f"<Bibliotheque user={self.utilisateur_id} jeu={self.jeu_id}>"