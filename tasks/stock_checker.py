from app import db, create_app
from app.models import Drug
from utils.mailer import envoyer_alerte_stock

def verifier_stock():
    app = create_app()
    with app.app_context():
        drugs = Drug.query.filter(Drug.quantity == 0).all()
        for drug in drugs:
            envoyer_alerte_stock(drug.name, 'admin@pharmacie.com')
