from collections import defaultdict
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models import Category, Drug, LossRecord
from app.forms import DeleteDrugForm, DrugForm, LossForm
from app import db
from app.routes.supplier import staff_required

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
    expiring_soon = request.args.get('expiring_soon')
    selected_category = request.args.get('category', type=int)

    # Base query
    query = Drug.query

    # Filtrer par catégorie si sélectionnée
    if selected_category:
        query = query.filter_by(category_id=selected_category)

    # Récupération des médicaments
    drugs = query.all()

    # Appliquer filtre expirant bientôt (en mémoire car méthode Python)
    if expiring_soon:
        drugs = [d for d in drugs if d.will_expire_soon(30)]

    # Charger les catégories pour le menu de filtre
    categories = Category.query.all()

    delete_form_drug = DeleteDrugForm()

    return render_template(
        'drugs/list.html',
        drugs=drugs,
        categories=categories,
        selected_category=selected_category,
        expiring_soon=expiring_soon,
        delete_form_drug=delete_form_drug
    )

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_drug():
    form = DrugForm()
    if form.validate_on_submit():
        category_id = form.category.data if form.category.data != 0 else None
        drug = Drug(
            name=form.name.data,
            price=form.price.data,
            unit=form.unit.data or 'unité',
            expiration_date=form.expiration_date.data,
            category_id=category_id
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

    # Remplir les choix de catégories
    form.category.choices = [(0, '— Aucune —')] + [(c.id, c.name) for c in Category.query.order_by(Category.name)]

    # Pré-remplir la catégorie existante
    if request.method == 'GET':
        form.category.data = drug.category_id or 0

    if form.validate_on_submit():
        drug.name = form.name.data
        drug.price = form.price.data
        drug.unit = form.unit.data or 'unité'
        drug.expiration_date = form.expiration_date.data
        drug.category_id = form.category.data or None 
        db.session.commit()
        flash(f'Médicament "{drug.name}" mis à jour.', 'success')
        return redirect(url_for('drug.list_drugs'))
    return render_template('drugs/edit.html', form=form, drug=drug)

@bp.route('/delete/<int:drug_id>', methods=['POST'])
@login_required
@admin_required
def delete_drug(drug_id):
    drug = Drug.query.get_or_404(drug_id)

    if drug.current_stock() > 0:
        flash("Impossible de supprimer un médicament encore en stock.", "warning")
        return redirect(url_for('drug.list_drugs'))

    db.session.delete(drug)
    db.session.commit()
    flash(f'Médicament "{drug.name}" supprimé avec succès.', 'success')
    return redirect(url_for('drug.list_drugs'))

# ---- AJOUT: gestion des pertes ----

@bp.route('/loss/new/<int:drug_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def new_loss(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    form = LossForm(drug_id=drug_id)

    form.drug_id.choices = [(drug.id, drug.name)]

    if form.validate_on_submit():
        # Récupération sécurisée du médicament par formulaire
        drug = Drug.query.get_or_404(int(form.drug_id.data))

        if drug.current_stock() < form.quantity.data:
            flash(f"Quantité de perte trop élevée (stock: {drug.current_stock()}).", "danger")
            return redirect(url_for('drug.new_loss', drug_id=drug.id))

        loss = LossRecord(
            drug_id=drug.id,
            quantity=form.quantity.data,
            reason=form.reason.data,
            comment=form.comment.data
        )
        db.session.add(loss)
        db.session.commit()
        flash(f"Pertes enregistrées pour {form.quantity.data} {drug.unit}(s) de {drug.name}.", "success")
        return redirect(url_for('drug.list_drugs'))

    return render_template('drugs/loss_new.html', form=form, drug=drug)

@bp.route('/losses')
@login_required
@admin_required
def list_losses():
    # Récupération des paramètres GET
    drug_id = request.args.get('drug_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Base de la requête
    query = LossRecord.query

    # Filtrer par médicament
    if drug_id:
        query = query.filter(LossRecord.drug_id == int(drug_id))

    # Filtrer par date de début
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(LossRecord.date >= start)
        except ValueError:
            pass  # Date invalide ignorée

    # Filtrer par date de fin
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Inclusif
            query = query.filter(LossRecord.date < end)
        except ValueError:
            pass

    # Exécuter la requête triée par date décroissante
    losses = query.order_by(LossRecord.date.desc()).all()

    # Récupérer la liste des médicaments pour le filtre
    drugs = Drug.query.order_by(Drug.name).all()

    # Calcul du total des quantités perdues
    total_quantity = sum(loss.quantity for loss in losses)

    # Données pour le graphique : pertes par jour
    chart_data = defaultdict(int)

    for loss in losses:
        key = loss.date.strftime('%Y-%m-%d')
        chart_data[key] += loss.quantity

    # On trie les dates
    labels = sorted(chart_data.keys())
    quantities = [chart_data[date] for date in labels]

    return render_template('drugs/losses_list.html', losses=losses, drugs=drugs, total_quantity=total_quantity, chart_labels=labels,
    chart_data=quantities)


@bp.route('/drug/<int:drug_id>/history')
@login_required
@staff_required
def drug_history(drug_id):
    drug = Drug.query.get_or_404(drug_id)
    purchases = [item for item in drug.purchase_items]
    sales = drug.sales
    losses = drug.losses
    return render_template('drugs/history.html', drug=drug, purchases=purchases, sales=sales, losses=losses)

@bp.route('/drug/expiring')
@login_required
@staff_required
def expiring_soon():
    drugs = Drug.query.all()
    expiring = [d for d in drugs if d.will_expire_soon(30)]
    return render_template('drugs/expiring.html', drugs=expiring, current_time=datetime.utcnow())