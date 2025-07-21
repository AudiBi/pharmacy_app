from flask import Blueprint, redirect, render_template, flash, url_for, request
from flask_login import login_required, current_user
from markupsafe import Markup
from app.models import Drug, Supplier, Sale
from datetime import date, timedelta, datetime
from app import socketio
import random

bp = Blueprint('dashboard', __name__)

# Stockage temporaire (exemple)
sales = []
alerts = []
LOW_STOCK_THRESHOLD = 5

def get_current_stock(drug_name):
    return random.randint(0, 10)  # Simule le stock restant

def add_alert(msg):
    alerts.append(msg)
    socketio.emit('new_alert', {'message': msg})

@bp.route('/dashboard')
@login_required
def dashboard():
    total_stock = sum(drug.quantity for drug in Drug.query.all())
    
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    ventes_du_jour = sum(sale.quantity for sale in Sale.query.filter(Sale.date >= today_start).all())
    
    # Préparer données initiales du graphique (labels = heures, data = CA cumulatif)
    labels = [dt.strftime("%H:%M:%S") for dt, _ in sales]
    cumul = 0
    data = []
    for _, montant in sales:
        cumul += montant
        data.append(cumul)

    common_data = dict(
        total_stock=total_stock,
        ventes_du_jour=ventes_du_jour,
        alerts=alerts,
        sales_labels=labels,
        sales_data=data,
    )

    if current_user.role == 'admin':
        return render_template('dashboards/admin_dashboard.html', **common_data)
    elif current_user.role == 'pharmacien':
        return render_template('dashboards/pharmacien_dashboard.html', **common_data)
    elif current_user.role == 'vendeur':
        return render_template('dashboards/vendeur_dashboard.html', **common_data)
    else:
        flash("Rôle inconnu ou non autorisé", "danger")
        return redirect(url_for('logout'))


# @bp.route('/dashboard')
# @login_required
# def dashboard():
#     # Statistiques communes
#     total_drugs = Drug.query.count()
#     total_sales = Sale.query.count()

#     # Données d'alertes
#     low_stock_threshold = 10
#     today = date.today()
#     soon_limit = today + timedelta(days=30)

#     expired_count = Drug.query.filter(Drug.expiration_date < today).count()
#     low_stock_count = Drug.query.filter(Drug.quantity <= low_stock_threshold).count()
#     soon_expired_count = Drug.query.filter(
#         Drug.expiration_date >= today,
#         Drug.expiration_date <= soon_limit
#     ).count()

#     alerts = []
#     if expired_count > 0:
#         alerts.append(f"{expired_count} périmé(s)")
#     if low_stock_count > 0:
#         alerts.append(f"{low_stock_count} en stock faible")
#     if soon_expired_count > 0:
#         alerts.append(f"{soon_expired_count} bientôt périmé(s)")

#     if alerts:
#         flash(Markup(' — '.join(alerts) + f' ! <a href="{url_for("stock.alerts")}" class="alert-link">Voir les alertes</a>'), 'warning')

#     if current_user.role == 'admin':
#         total_suppliers = Supplier.query.count()
#         return render_template('dashboard/dashboard_admin.html',
#                                total_drugs=total_drugs,
#                                total_sales=total_sales,
#                                total_suppliers=total_suppliers,
#                                expired_count=expired_count,
#                                low_stock_count=low_stock_count,
#                                soon_expired_count=soon_expired_count)
#     else:
#         return render_template('dashboard/dashboard_employee.html',
#                                total_drugs=total_drugs,
#                                total_sales=total_sales)





