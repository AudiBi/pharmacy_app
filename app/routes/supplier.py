from operator import or_
from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from app.models import Supplier, Purchase
from app.forms import DeleteSupplierForm, SupplierForm
from app import db
from flask_paginate import Pagination, get_page_parameter

bp = Blueprint('supplier', __name__, url_prefix='/suppliers')

# Autorisation pour admin OU pharmacien
def staff_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'pharmacien']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

#  Lister tous les fournisseurs
@bp.route('/')
@login_required
def list_suppliers():
    query = Supplier.query

    # Tri
    sort = request.args.get('sort', 'name')
    order = request.args.get('order', 'asc')
    if hasattr(Supplier, sort):
        column = getattr(Supplier, sort)
        query = query.order_by(column.desc() if order == 'desc' else column.asc())

    # Pagination
    page = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=10)
    suppliers = pagination.items

    
    delete_form_supplier = DeleteSupplierForm()
      
    return render_template('suppliers/list.html', suppliers=suppliers, pagination=pagination, delete_form_supplier=delete_form_supplier)

#  Ajouter un fournisseur
@bp.route('/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier(
            name=form.name.data,
            contact=form.contact.data,
            address=form.address.data
        )
        db.session.add(supplier)
        db.session.commit()
        flash(f'Fournisseur "{supplier.name}" ajouté.', 'success')
        return redirect(url_for('supplier.list_suppliers'))
    return render_template('suppliers/add.html', form=form)

# Modifier un fournisseur
@bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    form = SupplierForm(obj=supplier)
    if form.validate_on_submit():
        supplier.name = form.name.data
        supplier.contact = form.contact.data
        supplier.address = form.address.data
        db.session.commit()
        flash(f'Fournisseur "{supplier.name}" mis à jour.', 'success')
        return redirect(url_for('supplier.list_suppliers'))
    return render_template('suppliers/edit.html', form=form, supplier=supplier)

# Supprimer un fournisseur
@bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
@staff_required
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if supplier.purchases:
        flash("Impossible de supprimer un fournisseur avec des achats associés.", "danger")
        return redirect(url_for('supplier.list_suppliers'))
    db.session.delete(supplier)
    db.session.commit()
    flash(f'Fournisseur "{supplier.name}" supprimé.', 'success')
    return redirect(url_for('supplier.list_suppliers'))

# Voir l'historique des achats liés à un fournisseur
@bp.route('/<int:supplier_id>/purchases')
@login_required
@staff_required
def supplier_purchases(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    purchases = supplier.purchases 
    return render_template('suppliers/purchases.html', supplier=supplier, purchases=purchases)
