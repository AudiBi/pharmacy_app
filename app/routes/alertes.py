from flask import Blueprint, render_template, request
from app.models import Drug
from app import db

bp = Blueprint('alerts', __name__, url_prefix='/alertes')

@bp.route('/', methods=['GET'])
def stock_alerts():
    query = db.session.query(Drug)
    filters = {}

    nom = request.args.get('nom', '')
    categorie = request.args.get('categorie', '')
    stock = request.args.get('stock', '')

    if nom:
        query = query.filter(Drug.name.ilike(f"%{nom}%"))
        filters['nom'] = nom

    if categorie:
        query = query.filter(Drug.category == categorie)
        filters['categorie'] = categorie

    if stock == 'rupture':
        query = query.filter(Drug.quantity == 0)
        filters['stock'] = stock
    elif stock == 'faible':
        query = query.filter(Drug.quantity < 5)
        filters['stock'] = stock

    drugs = query.all()
    return render_template('alerts.html', drugs=drugs, filters=filters)
