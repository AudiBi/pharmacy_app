from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Drug
from datetime import date
from datetime import timedelta

bp = Blueprint('stock', __name__, url_prefix='/stock')

@bp.route('/alerts')
@login_required
def alerts():
    low_stock_threshold = 10
    low_stock_drugs = Drug.query.filter(Drug.quantity <= low_stock_threshold).all()
    expired_drugs = Drug.query.filter(Drug.expiration_date < date.today()).all()
    soon_limit = date.today() + timedelta(days=30)
    soon_expired_drugs = Drug.query.filter(
        Drug.expiration_date >= date.today(),
        Drug.expiration_date <= soon_limit
    ).all()

    return render_template('alerts_stock.html',
                           low_stock_drugs=low_stock_drugs,
                           expired_drugs=expired_drugs,
                           soon_expired_drugs=soon_expired_drugs)
