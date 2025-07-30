from datetime import datetime
from flask import Blueprint, render_template, redirect, request, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Drug, Payment, ReturnRecord, Sale, SaleItem, User
from app.forms import SaleForm
from app import db
from sqlalchemy.orm import joinedload

from app.routes.supplier import staff_required

bp = Blueprint('sale', __name__, url_prefix='/sales')

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    form = SaleForm()
    drugs = Drug.query.order_by(Drug.name).all()
    drug_choices = [(d.id, d.name) for d in drugs]

    for item_form in form.items:
        item_form.form.drug_id.choices = drug_choices

    if form.validate_on_submit():
        sale = Sale(user_id=current_user.id)
        db.session.add(sale)

        total_calculé = 0

        for item_data in form.items.data:
            drug = Drug.query.get(item_data['drug_id'])
            qty = item_data['quantity']

            if not drug:
                flash("Médicament introuvable.", "danger")
                return redirect(url_for('sale.new_sale'))

            if drug.is_expired():
                flash(f"{drug.name} est expiré.", "danger")
                return redirect(url_for('sale.new_sale'))

            if drug.current_stock() < qty:
                flash(f"Stock insuffisant pour {drug.name}.", "warning")
                return redirect(url_for('sale.new_sale'))

            item = SaleItem(
                drug_id=drug.id,
                quantity=qty,
                unit_price=drug.price
            )
            total_calculé += item.total_price
            sale.items.append(item)

        # Vérification du montant payé
        if form.amount_paid.data < total_calculé:
            flash("Montant payé insuffisant.", "danger")
            return redirect(url_for('sale.new_sale'))

        # Paiement
        payment = Payment(
            sale=sale,
            amount_paid=form.amount_paid.data,
            payment_method=form.payment_method.data
        )
        db.session.add(payment)

        db.session.commit()
        flash("Vente et paiement enregistrés avec succès", "success")
        return redirect(url_for('sale.sale_receipt', sale_id=sale.id))

    return render_template('sales/new.html', form=form, drug_list=drugs)

@bp.route('/receipt/<int:sale_id>')
@login_required
def sale_receipt(sale_id):
    sale = Sale.query.options(
        joinedload(Sale.items).joinedload(SaleItem.drug),  # utilise l'attribut de classe, pas une chaîne
        joinedload(Sale.user)
    ).get_or_404(sale_id)

    return render_template('sales/receipt.html', sale=sale)

@bp.route('/history/<int:sale_id>')
@login_required
def history(sale_id):
    sale = Sale.query.options(
        joinedload(Sale.items).joinedload(SaleItem.drug), 
        joinedload(Sale.user)
    ).get_or_404(sale_id)

    return render_template('sales/history.html', sale=sale)

@bp.route('/list')
@login_required
def list_sales():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    user_id = request.args.get('user_id', type=int)

    # Base query avec jointures
    query = Sale.query.options(joinedload(Sale.user)).join(Sale.user)

    # Filtrer par utilisateur si fourni
    if user_id:
        query = query.filter(Sale.user_id == user_id)

    # Filtrer par nom de médicament (optionnel)
    if search:
        query = query.join(Sale.items).join(SaleItem.drug)
        query = query.filter(Drug.name.ilike(f"%{search}%"))

    # Filtrer par date
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Sale.date >= start)
        except ValueError:
            flash("Format de date invalide (début)", "warning")

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(Sale.date <= end)
        except ValueError:
            flash("Format de date invalide (fin)", "warning")

    sales = query.order_by(Sale.date.desc()).paginate(page=page, per_page=10)
    users = User.query.order_by(User.username).all()
    total_sales = sum(sale.total_amount for sale in sales.items)

    return render_template('sales/list.html',
                           sales=sales,
                           users=users,
                           user_id=user_id,
                           search=search,
                           total_sales=total_sales,
                           start_date=start_date,
                           end_date=end_date)

@bp.route('/edit/<int:sale_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_sale(sale_id):
    sale = Sale.query.options(joinedload(Sale.items)).get_or_404(sale_id)
    form = SaleForm()

    drugs = Drug.query.order_by(Drug.name).all()
    drug_choices = [(d.id, d.name) for d in drugs]

    for item_form in form.items:
        item_form.form.drug_id.choices = drug_choices

    if form.validate_on_submit():
        # Supprimer les anciens items
        for item in sale.items:
            db.session.delete(item)

        # Ajouter les nouveaux items
        for item_form in form.items.data:
            drug = Drug.query.get(item_form['drug_id'])
            quantity = item_form['quantity']

            if not drug:
                flash("Médicament introuvable.", "danger")
                return redirect(url_for('sale.edit_sale', sale_id=sale.id))
            if drug.is_expired():
                flash(f"{drug.name} est expiré.", "danger")
                return redirect(url_for('sale.edit_sale', sale_id=sale.id))
            if drug.current_stock() + get_existing_quantity(sale, drug.id) < quantity:
                flash(f"Stock insuffisant pour {drug.name}.", "danger")
                return redirect(url_for('sale.edit_sale', sale_id=sale.id))

            sale_item = SaleItem(
                drug_id=drug.id,
                quantity=quantity,
                unit_price=drug.price
            )
            sale.items.append(sale_item)

        db.session.commit()
        flash("Vente modifiée avec succès.", "success")
        return redirect(url_for('sale.sale_receipt', sale_id=sale.id))

    # Pré-remplir les valeurs actuelles dans le formulaire (optionnel si WTForms permet)
    return render_template('sales/edit.html', form=form, sale=sale)


def get_existing_quantity(sale, drug_id):
    """
    Permet de connaître la quantité déjà vendue dans la vente d'origine pour un médicament donné.
    Utile pour recalculer le stock réel dispo.
    """
    for item in sale.items:
        if item.drug_id == drug_id:
            return item.quantity
    return 0


@bp.route('/delete/<int:sale_id>', methods=['POST'])
@login_required
@admin_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    flash("Vente annulée avec succès.", "info")
    return redirect(url_for('sale.list_sales'))

@bp.route('/return/<int:sale_item_id>', methods=['GET', 'POST'])
@login_required
def return_item(sale_item_id):
    sale_item = SaleItem.query.options(joinedload(SaleItem.drug)).get_or_404(sale_item_id)

    if request.method == 'POST':
        try:
            qty_returned = int(request.form.get('quantity'))
            reason = request.form.get('reason', '')
        except ValueError:
            flash("Quantité invalide.", "danger")
            return redirect(request.url)

        if qty_returned <= 0:
            flash("Quantité doit être supérieure à 0.", "danger")
            return redirect(request.url)

        if qty_returned > sale_item.net_quantity_sold:
            flash("Retour dépasse la quantité vendue restante.", "danger")
            return redirect(request.url)

        return_record = ReturnRecord(
            sale_item_id=sale_item.id,
            quantity=qty_returned,
            reason=reason
        )
        db.session.add(return_record)
        db.session.commit()

        flash(f"{qty_returned} {sale_item.drug.name} retourné avec succès.", "success")
        return redirect(url_for('sale.sale_receipt', sale_id=sale_item.sale_id))

    return render_template('sales/return_item.html', sale_item=sale_item)

@bp.route('/returns')
@login_required
@staff_required
def list_returns():
    returns = ReturnRecord.query.order_by(ReturnRecord.date.desc()).limit(100).all()
    return render_template('sales/returns.html', returns=returns)


@bp.route('/return-receipt/<int:return_id>')
@login_required
def return_receipt(return_id):
    return_record = ReturnRecord.query.options(
        joinedload(ReturnRecord.sale_item).joinedload(SaleItem.drug),
        joinedload(ReturnRecord.sale_item).joinedload(SaleItem.sale)
    ).get_or_404(return_id)

    return render_template('sales/return_receipt.html', return_record=return_record)