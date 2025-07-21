from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import Drug, LossRecord
from app.forms import DrugForm, LossForm
from app import db

bp = Blueprint('drug', __name__, url_prefix='/drugs')

# Décorateur simple pour restreindre aux admins
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
def list_drugs():
    drugs = Drug.query.all()
    return render_template('drugs/list.html', drugs=drugs)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_drug():
    form = DrugForm()
    if form.validate_on_submit():
        drug = Drug(
            name=form.name.data,
            quantity=form.quantity.data,
            price=form.price.data,
            unit=form.unit.data or 'unité',
            expiration_date=form.expiration_date.data
        )
        db.session.add(drug)
        db.session.commit()
        flash(f'Médicament "{drug.name}" ajouté avec succès.', 'success')
        return redirect(url_for('drug.list_drugs'))
    return render_template('drugs/add.html', form=form)

@bp.route('/edit/<int:drug_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_drug(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    form = DrugForm(obj=drug)
    if form.validate_on_submit():
        drug.name = form.name.data
        drug.quantity = form.quantity.data
        drug.price = form.price.data
        drug.unit = form.unit.data or 'unité'
        drug.expiration_date = form.expiration_date.data
        db.session.commit()
        flash(f'Médicament "{drug.name}" mis à jour.', 'success')
        return redirect(url_for('drug.list_drugs'))
    return render_template('drugs/edit.html', form=form, drug=drug)

# ---- AJOUT: gestion des pertes ----

@bp.route('/loss/new/<int:drug_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def new_loss(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    form = LossForm()
    if form.validate_on_submit():
        if drug.quantity < form.quantity.data:
            flash(f"Quantité de perte trop élevée (stock: {drug.quantity}).", "danger")
            return redirect(url_for('drug.new_loss', drug_id=drug_id))

        loss = LossRecord(
            drug_id=drug.id,
            quantity=form.quantity.data,
            reason=form.reason.data
        )
        drug.quantity -= form.quantity.data
        db.session.add(loss)
        db.session.commit()
        flash(f"Pertes enregistrées pour {form.quantity.data} {drug.unit}(s) de {drug.name}.", "success")
        return redirect(url_for('drug.list_drugs'))

    return render_template('drugs/loss_new.html', form=form, drug=drug)

@bp.route('/losses')
@login_required
@admin_required
def list_losses():
    losses = LossRecord.query.order_by(LossRecord.date.desc()).all()
    drugs = Drug.query.all()
    return render_template('drugs/losses_list.html', losses=losses, drugs=drugs)