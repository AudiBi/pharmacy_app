import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Utilise le port Railway si défini, sinon 5000 en local
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    app.run(debug=debug, host='0.0.0.0', port=port)
