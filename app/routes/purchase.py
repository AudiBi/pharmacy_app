from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from app import db
from app.forms import PurchaseForm
from app.models import Purchase, Supplier, Drug

bp = Blueprint('purchase', __name__, url_prefix='/purchases')

@bp.route('/', methods=['GET'])
def list_purchases():
    purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).all()
    form = PurchaseForm()
    return render_template('list.html', purchases=purchases, form=form)

@bp.route('/add', methods=['GET', 'POST'])
def add_or_edit_purchase():
    form = PurchaseForm()
    if form.validate_on_submit():
        purchase = Purchase(
            supplier=form.supplier.data,
            drug=form.drug.data,
            quantity=form.quantity.data,
            unit_price=form.unit_price.data,
            total_cost=form.total_cost.data or form.quantity.data * form.unit_price.data,
            purchase_date=form.purchase_date.data or datetime.utcnow(),
            commentaire=form.commentaire.data
        )
        db.session.add(purchase)
        db.session.commit()
        flash('Achat ajouté avec succès.', 'success')
        return redirect(url_for('purchase.list_purchases'))
    purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).all()
    return render_template('list.html', purchases=purchases, form=form)

@bp.route('/edit/<int:purchase_id>', methods=['GET', 'POST'])
def edit_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    form = PurchaseForm(obj=purchase)
    if form.validate_on_submit():
        form.populate_obj(purchase)
        db.session.commit()
        flash('Achat modifié avec succès.', 'success')
        return redirect(url_for('purchase.list_purchases'))
    return render_template('list.html', purchases=Purchase.query.all(), form=form)

@bp.route('/delete/<int:purchase_id>', methods=['POST'])
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    flash('Achat supprimé.', 'info')
    return redirect(url_for('purchase.list_purchases'))