from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from math import ceil
from flask import Blueprint, render_template, redirect, send_file, url_for, flash, request, abort
from flask_login import login_required, current_user
import pandas as pd
from app.models import Category, Drug, LossRecord, PurchaseItem, Sale, SaleItem
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
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Base query
    query = Drug.query

    # Filtrer par catégorie si nécessaire
    if selected_category:
        query = query.filter_by(category_id=selected_category)

    # Cas particulier : filtrage "expiring soon" en mémoire
    if expiring_soon:
        # Pas possible d'utiliser paginate() directement ici, car will_expire_soon() est une méthode Python
        all_filtered = query.all()
        drugs_filtered = [d for d in all_filtered if d.will_expire_soon(30)]
        
        # Création d'une fausse pagination manuelle
        total = len(drugs_filtered)
        start = (page - 1) * per_page
        end = start + per_page
        items = drugs_filtered[start:end]

        # Création d'un objet pagination factice
        class ManualPagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = ceil(total / per_page) if per_page else 0
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None

            def __iter__(self):
                return iter(self.items)

        drugs = ManualPagination(items, page, per_page, total)

    else:
        # Pagination SQL native
        drugs = query.order_by(Drug.name).paginate(page=page, per_page=per_page, error_out=False)

    categories = Category.query.order_by(Category.name).all()
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
    page = request.args.get('page', 1, type=int)

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

    # Trier par date décroissante + appliquer la pagination
    paginated_losses = query.order_by(LossRecord.date.desc()).paginate(page=page, per_page=10)

    # Pour le graphique et le total, on utilise les éléments paginés seulement
    losses_on_page = paginated_losses.items

    # Récupérer la liste des médicaments pour le filtre
    drugs = Drug.query.order_by(Drug.name).all()

    # Calcul du total des quantités perdues
    total_quantity = sum(loss.quantity for loss in losses_on_page)

    # Données pour le graphique : pertes par jour
    chart_data = defaultdict(int)

    for loss in losses_on_page:
        key = loss.date.strftime('%Y-%m-%d')
        chart_data[key] += loss.quantity

    # On trie les dates
    labels = sorted(chart_data.keys())
    quantities = [chart_data[date] for date in labels]

    return render_template('drugs/losses_list.html', losses=losses_on_page, drugs=drugs, total_quantity=total_quantity, chart_labels=labels,
    chart_data=quantities)

@bp.route('/losses/export_excel')
@login_required
def export_losses():
    # Récupération des filtres GET
    drug_id = request.args.get('drug_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Requête de base
    query = LossRecord.query

    # Filtres
    if drug_id:
        query = query.filter(LossRecord.drug_id == drug_id)
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(LossRecord.date >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(LossRecord.date <= end)
        except ValueError:
            pass

    losses = query.order_by(LossRecord.date.desc()).all()

    # Format des données pour Excel
    data = [{
        "Médicament": loss.drug.name if loss.drug else '',
        "Quantité perdue": loss.quantity,
        "Date de perte": loss.date.strftime('%d/%m/%Y %H:%M'),
        "Motif": loss.reason or '',
        "Commentaire": loss.comment or ''
    } for loss in losses]

    df = pd.DataFrame(data)

    # Création du fichier Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Pertes', index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name='pertes_filtrees.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/drugs/export_excel')
@login_required
def export_excel():
    category_id = request.args.get("category", type=int)
    expiring_soon = request.args.get("expiring_soon") == "1"

    # Base query
    query = Drug.query

    if category_id:
        query = query.filter_by(category_id=category_id)

    if expiring_soon:
        query = query.filter(Drug.expiration_date <= datetime.utcnow() + timedelta(days=30))

    drugs = query.all()

    # Préparer les données
    data = [{
        "Nom": drug.name,
        "Quantité": drug.current_stock(),
        "Prix (HTG)": round(drug.price, 2),
        "Unité": drug.unit,
        "Expiration": drug.expiration_date.strftime('%d/%m/%Y'),
        "Catégorie": drug.category.name if drug.category else ''
    } for drug in drugs]

    df = pd.DataFrame(data)

    # Générer le fichier Excel en mémoire
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Médicaments')
    output.seek(0)

    return send_file(
        output,
        download_name='liste_medicaments.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/drug/<int:drug_id>/history')
@login_required
@admin_required
def drug_history(drug_id):
    drug = Drug.query.options(
        joinedload(Drug.purchase_items).joinedload(PurchaseItem.purchase),
        joinedload(Drug.sales).joinedload(SaleItem.sale),
        joinedload(Drug.losses)
    ).get_or_404(drug_id)

    # Récupération des pages dans les requêtes
    page_purchases = request.args.get('page_purchases', 1, type=int)
    page_sales = request.args.get('page_sales', 1, type=int)
    page_losses = request.args.get('page_losses', 1, type=int)

    per_page = 5  # nombre d’éléments par page

    ### ACHATS ###
    all_purchases = sorted(
        drug.purchase_items,
        key=lambda x: x.purchase.purchase_date,
        reverse=True
    )
    total_purchases = len(all_purchases)
    purchases = all_purchases[(page_purchases - 1) * per_page: page_purchases * per_page]

    ### VENTES ###
    all_sales = sorted(
        drug.sales,
        key=lambda x: x.sale.date if x.sale else datetime.min,
        reverse=True
    )
    total_sales = len(all_sales)
    sales = all_sales[(page_sales - 1) * per_page: page_sales * per_page]

    ### PERTES ###
    all_losses = sorted(
        drug.losses,
        key=lambda x: x.date,
        reverse=True
    )
    total_losses = len(all_losses)
    losses = all_losses[(page_losses - 1) * per_page: page_losses * per_page]

    # Calcul des pages totales
    def pagination_dict(current_page, total_items):
        total_pages = ceil(total_items / per_page)
        return {
            'page': current_page,
            'pages': total_pages,
            'total': total_items,
            'has_prev': current_page > 1,
            'has_next': current_page < total_pages,
            'prev_num': current_page - 1,
            'next_num': current_page + 1,
        }

    return render_template(
        'drugs/history.html',
        drug=drug,
        purchases=purchases,
        sales=sales,
        losses=losses,
        pagination_purchases=pagination_dict(page_purchases, total_purchases),
        pagination_sales=pagination_dict(page_sales, total_sales),
        pagination_losses=pagination_dict(page_losses, total_losses)
    )

@bp.route('/drug/expiring')
@login_required
@staff_required
def expiring_soon():
    drugs = Drug.query.all()
    expiring = [d for d in drugs if d.will_expire_soon(30)]
    return render_template('drugs/expiring.html', drugs=expiring, current_time=datetime.utcnow())

@bp.route('/top-drugs')
@login_required
@admin_required
def top_drugs():
    # Exemple: récupérer les 10 médicaments les plus vendus par quantité
    top_drugs_data = db.session.query(
        SaleItem.drug_id,
        func.sum(SaleItem.quantity).label('total_qty')
    ).group_by(SaleItem.drug_id).order_by(func.sum(SaleItem.quantity).desc()).limit(10).all()

    # Récupérer les noms des médicaments
    drugs = []
    names = []
    quantities = []

    for drug_id, total_qty in top_drugs_data:
        drug = db.session.query(Drug).get(drug_id)
        if drug:
            drugs.append({'name': drug.name, 'total_qty': total_qty})
            names.append(drug.name)
            quantities.append(total_qty)

    return render_template('reports/top_drugs.html', drugs=drugs, names=names, quantities=quantities)

@bp.route('/stock-alert')
@login_required
@admin_required
def stock_alert():
    seuil = 5  # seuil de stock bas
    page = request.args.get('page', 1, type=int)
    per_page = 10

    all_drugs = Drug.query.all()
    low_stock_drugs = []

    for drug in all_drugs:
        stock = drug.current_stock()
        if stock < seuil:
            drug.current_stock_calculated = stock  # attribut temporaire
            low_stock_drugs.append(drug)

    total = len(low_stock_drugs)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_drugs = low_stock_drugs[start:end]

    pagination = ManualPagination(paginated_drugs, page, per_page, total)

    return render_template(
        "reports/stock_alert.html",
        drugs=pagination,
        seuil=seuil
    )


@bp.route('/ruptures-stock')
@login_required
@admin_required
def stock_out_view():
    seuil = 0  # rupture = stock == 0
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Récupérer tous les médicaments en rupture
    all_ruptures = [drug for drug in Drug.query.all() if drug.current_stock() == seuil]

    total = len(all_ruptures)
    total_pages = ceil(total / per_page)

    start = (page - 1) * per_page
    end = start + per_page
    ruptures = all_ruptures[start:end]

    # Si tu veux ajouter un attribut temporaire (optionnel)
    for drug in ruptures:
        drug.current_stock_calculated = drug.current_stock()

    return render_template(
        'reports/ruptures_stock.html',
        ruptures=ruptures,
        page=page,
        total_pages=total_pages
    )


class ManualPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = ceil(total / per_page) if per_page else 1

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None