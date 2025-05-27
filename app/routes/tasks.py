from app import db
from app.models import Drug
from app import create_app

app = create_app()

def verifier_stock():
    with app.app_context():
        drugs = db.session.query(Drug).all()
        for drug in drugs:
            if drug.quantity == 0:
                # Logique pour alerter l'administrateur
                pass

scheduler.add_job(verifier_stock, CronTrigger(hour=0, minute=0))
