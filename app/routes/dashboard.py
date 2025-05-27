from flask import Blueprint, render_template, flash, url_for
from markupsafe import Markup
from flask_login import login_required, current_user
from app.models import Drug, Supplier, Sale
from datetime import date, timedelta

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
@login_required
def dashboard():
    # Statistiques communes
    total_drugs = Drug.query.count()
    total_sales = Sale.query.count()

    # Données d'alertes
    low_stock_threshold = 10
    today = date.today()
    soon_limit = today + timedelta(days=30)

    expired_count = Drug.query.filter(Drug.expiration_date < today).count()
    low_stock_count = Drug.query.filter(Drug.quantity <= low_stock_threshold).count()
    soon_expired_count = Drug.query.filter(
        Drug.expiration_date >= today,
        Drug.expiration_date <= soon_limit
    ).count()

    alerts = []
    if expired_count > 0:
        alerts.append(f"{expired_count} périmé(s)")
    if low_stock_count > 0:
        alerts.append(f"{low_stock_count} en stock faible")
    if soon_expired_count > 0:
        alerts.append(f"{soon_expired_count} bientôt périmé(s)")

    if alerts:
        flash(Markup(' — '.join(alerts) + f' ! <a href="{url_for("stock.alerts")}" class="alert-link">Voir les alertes</a>'), 'warning')

    if current_user.role == 'admin':
        total_suppliers = Supplier.query.count()
        return render_template('dashboard/dashboard_admin.html',
                               total_drugs=total_drugs,
                               total_sales=total_sales,
                               total_suppliers=total_suppliers,
                               expired_count=expired_count,
                               low_stock_count=low_stock_count,
                               soon_expired_count=soon_expired_count)
    else:
        return render_template('dashboard/dashboard_employee.html',
                               total_drugs=total_drugs,
                               total_sales=total_sales)





