from flask import Blueprint, render_template, request, redirect, flash, url_for, send_file
from flask_login import login_required
from app.models import Sale, LossRecord, Drug
from app import db
from datetime import datetime
import pandas as pd
import io
from sqlalchemy import func
from flask import jsonify

bp = Blueprint('history', __name__, url_prefix='/history')

@bp.route('/combined')
@login_required
def combined_history():
    drug_id = request.args.get('drug_id', type=int)
    entry_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    sales_query = Sale.query
    losses_query = LossRecord.query

    if drug_id:
        sales_query = sales_query.filter(Sale.drug_id == drug_id)
        losses_query = losses_query.filter(LossRecord.drug_id == drug_id)
    if start_date:
        sales_query = sales_query.filter(Sale.date >= start_date)
        losses_query = losses_query.filter(LossRecord.date >= start_date)
    if end_date:
        sales_query = sales_query.filter(Sale.date <= end_date)
        losses_query = losses_query.filter(LossRecord.date <= end_date)

    sales = [{
        'type': 'Vente',
        'drug': s.drug.name,
        'quantity': s.quantity,
        'date': s.date,
        'comment': 'Vente enregistrée'
    } for s in sales_query.all()] if entry_type in (None, 'Vente') else []

    losses = [{
        'type': 'Perte',
        'drug': l.drug.name,
        'quantity': l.quantity,
        'date': l.date,
        'comment': l.reason or 'Non spécifié',
        'id': l.id
    } for l in losses_query.all()] if entry_type in (None, 'Perte') else []

    history = sorted(sales + losses, key=lambda x: x['date'], reverse=True)
    drugs = Drug.query.order_by(Drug.name).all()

    return render_template('history/combined.html',
                           history=history,
                           drugs=drugs,
                           selected_drug=drug_id,
                           selected_type=entry_type,
                           start_date=start_date,
                           end_date=end_date)

@bp.route('/export/excel')
@login_required
def export_excel():
    # Appel interne pour récupérer les données filtrées
    drug_id = request.args.get('drug_id', type=int)
    entry_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    sales_query = Sale.query
    losses_query = LossRecord.query

    if drug_id:
        sales_query = sales_query.filter(Sale.drug_id == drug_id)
        losses_query = losses_query.filter(LossRecord.drug_id == drug_id)
    if start_date:
        sales_query = sales_query.filter(Sale.date >= start_date)
        losses_query = losses_query.filter(LossRecord.date >= start_date)
    if end_date:
        sales_query = sales_query.filter(Sale.date <= end_date)
        losses_query = losses_query.filter(LossRecord.date <= end_date)

    sales = [{
        'Type': 'Vente',
        'Médicament': s.drug.name,
        'Quantité': s.quantity,
        'Date': s.date,
        'Commentaire': 'Vente enregistrée'
    } for s in sales_query.all()] if entry_type in (None, 'Vente') else []

    losses = [{
        'Type': 'Perte',
        'Médicament': l.drug.name,
        'Quantité': l.quantity,
        'Date': l.date,
        'Commentaire': l.reason or 'Non spécifié'
    } for l in losses_query.all()] if entry_type in (None, 'Perte') else []

    history = sales + losses
    df = pd.DataFrame(history)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Historique')

    output.seek(0)
    return send_file(output, download_name="historique_sorties.xlsx", as_attachment=True)

@bp.route('/loss/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_loss(id):
    loss = LossRecord.query.get_or_404(id)
    if request.method == 'POST':
        loss.quantity = request.form['quantity']
        loss.reason = request.form['reason']
        db.session.commit()
        flash("Perte mise à jour.", "success")
        return redirect(url_for('history.combined_history'))
    return render_template('loss/edit.html', loss=loss)

@bp.route('/loss/<int:id>/delete', methods=['POST'])
@login_required
def delete_loss(id):
    loss = LossRecord.query.get_or_404(id)
    db.session.delete(loss)
    db.session.commit()
    flash("Perte supprimée.", "info")
    return redirect(url_for('history.combined_history'))


@bp.route('/charts')
@login_required
def charts():
    sales_data = (
        db.session.query(func.date(Sale.date), func.sum(Sale.quantity))
        .group_by(func.date(Sale.date))
        .order_by(func.date(Sale.date))
        .all()
    )
    loss_data = (
        db.session.query(func.date(LossRecord.date), func.sum(LossRecord.quantity))
        .group_by(func.date(LossRecord.date))
        .order_by(func.date(LossRecord.date))
        .all()
    )

    all_dates = sorted(set([d[0] for d in sales_data] + [d[0] for d in loss_data]))
    sales_dict = {d[0]: d[1] for d in sales_data}
    loss_dict = {d[0]: d[1] for d in loss_data}

    labels = [d.strftime('%Y-%m-%d') for d in all_dates]
    sales = [sales_dict.get(d, 0) for d in all_dates]
    losses = [loss_dict.get(d, 0) for d in all_dates]

    # --- CALCUL RÉGRESSION LINÉAIRE ---
    def calc_trend(data):
        if len(data) < 2:
            return [data[0] if data else 0] * len(data)
        x = np.arange(len(data))
        y = np.array(data)
        coef = np.polyfit(x, y, 1)  # y = ax + b
        trend = np.poly1d(coef)(x)
        return trend.tolist()

    trend_sales = calc_trend(sales)
    trend_losses = calc_trend(losses)

    chart_data = {
        'labels': labels,
        'sales': sales,
        'losses': losses,
        'sales_trend': trend_sales,
        'losses_trend': trend_losses,
    }

    return render_template('history/charts.html', chart_data=chart_data)
