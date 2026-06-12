from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True : rechargement auto + erreurs détaillées. JAMAIS en prod.
    app.run(debug=True)