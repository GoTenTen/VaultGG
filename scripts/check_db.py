# check_db.py — vérif rapide du contenu enrichi, à supprimer après.
# Pas besoin du binaire sqlite3 : le module sqlite3 est dans la stdlib Python.
import sqlite3

con = sqlite3.connect("vaultgg.db")
cur = con.cursor()

print("=== Jeux enrichis (note) ===")
for nom, note in cur.execute(
    "SELECT nom, note_igbd FROM jeu WHERE note_igbd IS NOT NULL LIMIT 10"
):
    print(f"  {note:.1f}  {nom}")

print("\n=== Genres en base ===")
for (libelle,) in cur.execute("SELECT libelle FROM genre"):
    print(f"  {libelle}")

print("\n=== Genres de Skyrim ===")
for nom, libelle in cur.execute("""
    SELECT j.nom, g.libelle
    FROM jeu j
    JOIN jeu_genre jg ON jg.jeu_id = j.id
    JOIN genre g ON g.id = jg.genre_id
    WHERE j.nom LIKE '%Skyrim%'
"""):
    print(f"  {nom} -> {libelle}")

con.close()