from datetime import datetime
from flask import Blueprint, render_template, redirect, request, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Drug, Sale
from app.forms import SaleForm
from app import db

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
    # Remplir les choix de médicaments (id, nom)
    form.drug_id.choices = [(d.id, d.name) for d in Drug.query.order_by(Drug.name).all()]

    if form.validate_on_submit():
        drug = Drug.query.get(form.drug_id.data)
        if not drug:
            flash("Médicament introuvable.", "danger")
            return redirect(url_for('sale.new_sale'))
        if drug.quantity < form.quantity.data:
            flash(f"Stock insuffisant pour {drug.name} (disponible: {drug.quantity}).", "danger")
            return redirect(url_for('sale.new_sale'))
        # Création de la vente
        sale = Sale(drug_id=drug.id, quantity=form.quantity.data)
        drug.quantity -= form.quantity.data
        db.session.add(sale)
        db.session.commit()
        flash(f"Vente de {form.quantity.data} {drug.unit}(s) de {drug.name} enregistrée.", "success")
        return redirect(url_for('sale.history'))
    return render_template('sales/new.html', form=form)

@bp.route('/history')
@login_required
def history():
    sales = Sale.query.order_by(Sale.date.desc()).all()
    return render_template('sales/history.html', sales=sales)

@bp.route('/list')
@login_required
def list_sales():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)

    query = Sale.query.join(Drug)

    if search:
        query = query.filter(Drug.name.ilike(f"%{search}%"))

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

    return render_template('sales/list.html', sales=sales, search=search,
                           start_date=start_date, end_date=end_date)