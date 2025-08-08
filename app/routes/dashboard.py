from collections import defaultdict
from flask import Blueprint, redirect, render_template, flash, url_for
from flask_login import login_required, current_user
from sqlalchemy import extract, func
from sqlalchemy.orm import joinedload
from app.models import Drug, Payment, Purchase, ReturnRecord, SaleItem, Supplier, Sale, LossRecord, User
from datetime import date, timedelta, datetime
from app import socketio, db
import random

bp = Blueprint('dashboard', __name__)

alerts = []
LOW_STOCK_THRESHOLD = 5

def add_alert(msg):
    alerts.append(msg)
    socketio.emit('new_alert', {'message': msg})

def get_frequent_loss_reasons(limit=5):
    results = (
        db.session.query(LossRecord.reason, func.count(LossRecord.id).label('count'))
        .group_by(LossRecord.reason)
        .order_by(func.count(LossRecord.id).desc())
        .limit(limit)
        .all()
    )
    return results

def get_active_users_by_sales(days=7):
    since_date = datetime.utcnow() - timedelta(days=days)

    users = (
        User.query
        .join(Sale)
        .filter(Sale.date >= since_date)
        .options(joinedload(User.sales))
        .distinct()
        .all()
    )

    return users

@bp.route('/dashboard')
@login_required
def dashboard():
    total_stock = sum(drug.current_stock() for drug in Drug.query.all())

    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    today_end = today_start + timedelta(days=1)

    # Ventes du jour (Quantité)
    sales_today = Sale.query.options(joinedload(Sale.items))\
        .filter(Sale.date >= today_start, Sale.date < today_end).all()
    ventes_du_jour = sum(item.quantity for sale in sales_today for item in sale.items)

    # Produits proches de péremption
    today = datetime.utcnow().date()
    near_expiry = []
    for drug in Drug.query.all():
        if drug.expiration_date:
            days_left = (drug.expiration_date - today).days
            if 0 <= days_left <= 30:
                near_expiry.append((drug, days_left))
    near_expiry.sort(key=lambda x: x[1])

    # Achats du jour
    purchases_today = Purchase.query.filter(Purchase.purchase_date >= today_start,
                                            Purchase.purchase_date < today_end).all()
    ca_achats = sum(p.total_amount for p in purchases_today)

    ca_ventes = sum(sale.total_amount for sale in sales_today)
    # Paiements du jour
    payments_today = Payment.query.filter(Payment.payment_date >= today_start,
                                          Payment.payment_date < today_end).all()
    ca_payments = sum(p.amount_paid for p in payments_today)

    # Retours du jour
    returns_today = (db.session.query(func.sum(ReturnRecord.quantity * SaleItem.unit_price))
                     .join(SaleItem, ReturnRecord.sale_item_id == SaleItem.id)
                     .join(Sale, SaleItem.sale_id == Sale.id)
                     .filter(Sale.date >= today_start, Sale.date < today_end)
                     .scalar() or 0)

    # Pertes du jour
    loss_today = (db.session.query(func.sum(LossRecord.quantity))
                  .filter(LossRecord.date >= today_start, LossRecord.date < today_end)
                  .scalar() or 0)

    # Top 5 médicaments les plus vendus
    top5_meds = defaultdict(int)
    all_sales = Sale.query.options(joinedload(Sale.items)).all()
    for sale in all_sales:
        for item in sale.items:
            top5_meds[item.drug.name] += item.quantity
    top5_meds = sorted(top5_meds.items(), key=lambda x: x[1], reverse=True)[:5]

    # Chiffre d'affaires cumulé par heure
    ca_par_heure = defaultdict(float)
    for sale in all_sales:
        heure = sale.date.replace(minute=0, second=0, microsecond=0)
        ca_par_heure[heure] += sale.total_amount
    heures_tries = sorted(ca_par_heure.keys())
    labels = [h.strftime("%H:%M") for h in heures_tries]
    cumul = 0
    data = []
    for h in heures_tries:
        cumul += ca_par_heure[h]
        data.append(cumul)

    # Ventes hebdomadaires (unités & CA)
    today = datetime.utcnow()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=7)
    results = (
        Sale.query
        .join(Sale.items)
        .with_entities(
            extract('dow', Sale.date).label('day_of_week'),
            func.sum(SaleItem.quantity).label('total_units'),
            func.sum(SaleItem.quantity * SaleItem.unit_price).label('total_revenue')
        )
        .filter(Sale.date >= start_of_week, Sale.date < end_of_week)
        .group_by('day_of_week')
        .all()
    )
    weekly_sales = [0] * 7
    weekly_revenue = [0.0] * 7
    for day, units, revenue in results:
        index = (int(day) - 1) % 7
        weekly_sales[index] = int(units)
        weekly_revenue[index] = float(revenue)
    weekly_labels = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

    # Raisons les plus fréquentes de pertes
    loss_reasons = get_frequent_loss_reasons()
    active_users = get_active_users_by_sales(days=7)

    alerts.clear()  # Vider les alertes à chaque appel

    # Alertes stock faible
    for drug in Drug.query.all():
        stock = drug.current_stock()
        if stock <= LOW_STOCK_THRESHOLD:
            msg = f"Stock faible pour {drug.name} : {stock} unités restantes."
            add_alert(msg)

    # Alertes médicaments proches de péremption
    # today = datetime.utcnow().date()
    # for drug in Drug.query.all():
    #     if drug.expiration_date:
    #         days_left = (drug.expiration_date - today).days
    #         if 0 <= days_left <= 30:
    #             msg = f"{drug.name} proche de la péremption ({days_left} jours restants)."
    #             add_alert(msg)

    # Alerte pertes élevées aujourd’hui (seuil à adapter)
    PERTE_ELEVEE_SEUIL = 10
    if loss_today > PERTE_ELEVEE_SEUIL:
        msg = f"Pertes élevées aujourd’hui : {loss_today} unités perdues."
        add_alert(msg)

    common_data = dict(
        total_stock=total_stock,
        ventes_du_jour=ventes_du_jour,
        alerts=alerts,
        sales_labels=labels,
        sales_data=data,
        near_expiry=near_expiry,
        top5_meds=top5_meds,
        weekly_sales_labels=weekly_labels,
        weekly_sales_data=weekly_sales,
        weekly_revenue_data=weekly_revenue,
        ca_achats=ca_achats,
        ca_ventes=ca_ventes,
        ca_payments=ca_payments,
        returns_today=returns_today,
        loss_today=loss_today,
        loss_reasons=loss_reasons
    )

    if current_user.role == 'admin':
        return render_template('dashboards/admin_dashboard.html', active_users=active_users, **common_data)
    elif current_user.role == 'pharmacien':
        return render_template('dashboards/pharmacien_dashboard.html', **common_data)
    elif current_user.role == 'vendeur':
        return render_template('dashboards/vendeur_dashboard.html', **common_data)
    else:
        flash("Rôle inconnu ou non autorisé", "danger")
        return redirect(url_for('logout'))
