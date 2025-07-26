from collections import defaultdict
from flask import Blueprint, redirect, render_template, flash, url_for, request
from flask_login import login_required, current_user
from markupsafe import Markup
from app.models import Drug, Supplier, Sale
from datetime import date, timedelta, datetime
from sqlalchemy.orm import joinedload
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
    # Exemple : calcul du stock total
    total_stock = sum(drug.current_stock() for drug in Drug.query.all())

    # Plage de temps aujourd'hui
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    today_end = today_start + timedelta(days=1)

    # Récupérer toutes les ventes du jour avec leurs items
    sales = Sale.query.options(joinedload(Sale.items))\
        .filter(Sale.date >= today_start, Sale.date < today_end).all()

    # Quantité totale vendue aujourd'hui
    ventes_du_jour = sum(item.quantity for sale in sales for item in sale.items)

    # Exemple récupération des produits proches de péremption (< 30 jours)
    today = datetime.utcnow().date()
    near_expiry = []
    for drug in Drug.query.all():
        if drug.expiration_date:
            days_left = (drug.expiration_date - today).days
            if 0 <= days_left <= 30:
                near_expiry.append((drug, days_left))
    near_expiry.sort(key=lambda x: x[1])

    # Exemple top 5 médicaments les plus vendus (par quantité)
    sales_count = defaultdict(int)
    
    sales = Sale.query.all()
    for sale in sales:
        for item in sale.items:
            sales_count[item.drug.name] += item.quantity
    top5_meds = sorted(sales_count.items(), key=lambda x: x[1], reverse=True)[:5]

    # Calcul chiffre d'affaires par heure (regroupé)
    ca_par_heure = defaultdict(float)
    for sale in sales:
        heure = sale.date.replace(minute=0, second=0, microsecond=0)
        ca_par_heure[heure] += sale.total_amount  # Vérifie que total_amount existe

    heures_tries = sorted(ca_par_heure.keys())

    # Préparer labels et données cumulées pour le graphique
    labels = [h.strftime("%H:%M") for h in heures_tries]
    cumul = 0
    data = []
    for h in heures_tries:
        cumul += ca_par_heure[h]
        data.append(cumul)

    common_data = dict(
        total_stock=total_stock,
        ventes_du_jour=ventes_du_jour,
        alerts=alerts,
        sales_labels=labels,
        sales_data=data,
        near_expiry=near_expiry,
        top5_meds=top5_meds

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



