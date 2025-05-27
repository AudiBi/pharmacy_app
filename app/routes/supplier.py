from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Supplier
from app.forms import SupplierForm
from app import db

bp = Blueprint('supplier', __name__, url_prefix='/suppliers')

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
def list_suppliers():
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
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

@bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
@admin_required
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
