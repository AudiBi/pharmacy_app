from datetime import datetime, timedelta
from io import BytesIO
from flask import Blueprint, flash, redirect, render_template, request, jsonify, abort, send_file, url_for
from flask_login import login_required, current_user
import pandas as pd
from sqlalchemy import func
from app import db
from app.forms import PurchaseForm
from sqlalchemy.orm import joinedload
from app.models import Purchase, PurchaseItem, Supplier, Drug
from app.routes.supplier import staff_required

bp = Blueprint('purchase', __name__, url_prefix='/purchases')


@bp.route('/', methods=['GET'])
@login_required
@staff_required
def list_purchases():
    query = Purchase.query.options(joinedload(Purchase.items).joinedload(PurchaseItem.drug))

    supplier_id = request.args.get('supplier_id', type=int)
    drug_id = request.args.get('drug_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)

    if start_date:
        query = query.filter(Purchase.purchase_date >= start_date)

    if end_date:
        query = query.filter(Purchase.purchase_date <= end_date)

    # Si un médicament est sélectionné, ne garder que les achats contenant ce médicament
    if drug_id:
        query = query.join(Purchase.items).filter(PurchaseItem.drug_id == drug_id)

    purchases = query.order_by(Purchase.purchase_date.desc()).all()

    # Charger tous les fournisseurs et médicaments pour le filtre
    suppliers = Supplier.query.all()
    drugs = Drug.query.order_by(Drug.name).all()

    return render_template(
        'purchase/list.html',
        purchases=purchases,
        suppliers=suppliers,
        drugs=drugs
    )

@bp.route('/purchases/export_excel')
@login_required
def export_purchases():
    supplier_id = request.args.get('supplier_id')
    drug_id = request.args.get('drug_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Purchase.query

    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Purchase.purchase_date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(Purchase.purchase_date <= end)
        except ValueError:
            pass

    purchases = query.order_by(Purchase.purchase_date.desc()).all()

    data = []
    for purchase in purchases:
        for item in purchase.items:
            if drug_id and str(item.drug_id) != drug_id:
                continue

            data.append({
                "ID Achat": purchase.id,
                "Date": purchase.purchase_date.strftime('%d/%m/%Y %H:%M') if purchase.purchase_date else '',
                "Fournisseur": purchase.supplier.name,
                "Médicament": item.drug.name,
                "Quantité": item.quantity,
                "Prix Unitaire (HTG)": f"{item.unit_price:.2f}",
                "Total (HTG)": f"{item.total_price:.2f}"
            })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name="Achats", index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="liste_achats.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/new', methods=['GET', 'POST'])
@login_required
@staff_required
def new_purchase():
    form = PurchaseForm()

    if form.validate_on_submit():
        # Récupérer le fournisseur
        supplier_id = form.supplier.data
        supplier = Supplier.query.get(supplier_id)
        purchase_date = form.purchase_date.data or datetime.utcnow()
        commentaire = form.commentaire.data

        # Créer l'achat principal
        purchase = Purchase(
            supplier_id=supplier.id,
            purchase_date=purchase_date,
            commentaire=commentaire
        )
        db.session.add(purchase)
        db.session.flush()  # Flush pour récupérer purchase.id avant d'ajouter les items

        # Créer un PurchaseItem par produit acheté
        for item_form in form.items.entries:
            drug_id = item_form.form.drug_id.data
            quantity = item_form.form.quantity.data
            unit_price = item_form.form.unit_price.data
            total_cost = quantity * unit_price

            purchase_item = PurchaseItem(
                purchase_id=purchase.id,
                drug_id=drug_id,
                quantity=quantity,
                unit_price=unit_price
            )
            db.session.add(purchase_item)

        db.session.commit()
        flash('Achat enregistré avec succès.', 'success')
        return redirect(url_for('purchase.list_purchases'))

    return render_template('purchase/new.html', form=form)



@bp.route('/edit/<int:purchase_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_purchase(purchase_id):
    # Non applicable tel quel en mode multi-produits car chaque produit est une ligne distincte
    flash('Modification de plusieurs produits en un seul achat n\'est pas encore supportée.', 'warning')
    return redirect(url_for('purchase.list_purchases'))


@bp.route('/delete/<int:purchase_id>', methods=['POST'])
@login_required
@staff_required
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    flash('Achat supprimé.', 'info')
    return redirect(url_for('purchase.list_purchases'))


@bp.route('/purchase/<int:purchase_id>')
@login_required
@staff_required
def view_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    return render_template('purchase/view_purchase.html', purchase=purchase)

@bp.route('/empty_item_template')
@login_required
@staff_required
def empty_purchase_item():
    drugs = Drug.query.order_by(Drug.name).all()
    return render_template('purchase/empty_purchase_item.html', drugs=drugs)


@bp.route('/purchase_stats_by_supplier')
@login_required
def purchase_stats_by_supplier():
    days = int(request.args.get('days', 30))  # Par défaut : 30 jours
    since_date = datetime.utcnow() - timedelta(days=days)

    results = (
        db.session.query(
            Supplier.name,
            func.count(Purchase.id).label("nb_achats"),
            func.sum(PurchaseItem.quantity * PurchaseItem.unit_price).label("total_depense")
        )
        .join(Purchase, Purchase.supplier_id == Supplier.id)
        .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .filter(Purchase.purchase_date >= since_date)
        .group_by(Supplier.name)
        .order_by(func.sum(PurchaseItem.quantity * PurchaseItem.unit_price).desc())
        .all()
    )

    return render_template(
        'purchase/purchase_stats_by_supplier.html',
        stats=results,
        selected_days=days
    )