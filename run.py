from app import create_app

app = create_app()

if __name__ == '__main__':
    # Active le mode debug seulement en développement
    app.run(debug=True, host='0.0.0.0', port=5000)
