from datetime import datetime, timedelta
from io import BytesIO
from math import ceil
from flask import Blueprint, flash, redirect, render_template, request, jsonify, abort, send_file, url_for
from flask_login import login_required, current_user
import pandas as pd
from sqlalchemy import exists, func
from app import db
from app.forms import DeletePurchaseForm, EditPurchaseForm, PurchaseForm, PurchaseItemForm
from sqlalchemy.orm import joinedload
from app.models import Purchase, PurchaseItem, Sale, SaleItem, Supplier, Drug
from app.routes.supplier import staff_required
from sqlalchemy.exc import SQLAlchemyError

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
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre d’achats par page

    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)

    if start_date:
        query = query.filter(Purchase.purchase_date >= start_date)

    if end_date:
        query = query.filter(Purchase.purchase_date <= end_date)

    # Si un médicament est sélectionné, ne garder que les achats contenant ce médicament
    if drug_id:
        query = query.join(Purchase.items).filter(PurchaseItem.drug_id == drug_id)

    purchases = query.order_by(Purchase.purchase_date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    # Charger tous les fournisseurs et médicaments pour le filtre
    suppliers = Supplier.query.all()
    drugs = Drug.query.order_by(Drug.name).all()
    
    delete_form_purchase = DeletePurchaseForm()
    return render_template(
        'purchase/list.html',
        purchases=purchases,
        suppliers=suppliers,
        drugs=drugs,
        delete_form_purchase=delete_form_purchase 
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
    purchase = Purchase.query.options(joinedload(Purchase.items)).get_or_404(purchase_id)

    # 1. Vérifier si l'un des produits a été vendu après la date d'achat
    for item in purchase.items:
        has_been_sold = db.session.query(
            exists().where(
                (SaleItem.drug_id == item.drug_id) &
                (SaleItem.sale.has(SaleItem.sale.property.mapper.class_.date >= purchase.purchase_date))
            )
        ).scalar()

        if has_been_sold:
            flash(f"Le médicament '{item.drug.name}' a été vendu après cet achat. "
                  "Impossible de modifier ou supprimer cet achat.", "danger")
            return redirect(url_for('purchase.list_purchases'))

    # 2. Formulaire principal
    form = EditPurchaseForm(obj=purchase)

    # 3. Pré-remplir les items si GET
    if request.method == 'GET':
        form.items.entries = []
        for item in purchase.items:
            form.items.append_entry({
                'drug_id': item.drug_id,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price)
            })

    # 4. Charger les choix dynamiques pour chaque sous-formulaire
    drug_choices = [(d.id, f"{d.name} ({d.category.name if d.category else 'Sans catégorie'})")
                    for d in Drug.query.order_by(Drug.name).all()]
    for item_form in form.items:
        item_form.form.drug_id.choices = drug_choices

    # 5. Si le formulaire est soumis et valide
    if form.validate_on_submit():
        try:
            # Mise à jour des infos principales
            purchase.supplier_id = form.supplier_id.data
            purchase.purchase_date = form.purchase_date.data or datetime.utcnow()
            purchase.commentaire = form.commentaire.data

            # Supprimer les anciens items
            PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()

            # Ajouter les nouveaux items
            for item_form in form.items:
                new_item = PurchaseItem(
                    purchase=purchase,
                    drug_id=item_form.form.drug_id.data,
                    quantity=item_form.form.quantity.data,
                    unit_price=float(item_form.form.unit_price.data)
                )
                db.session.add(new_item)

            db.session.commit()
            flash("Achat mis à jour avec succès.", "success")
            return redirect(url_for('purchase.list_purchases'))

        except Exception as e:
            db.session.rollback()
            flash("Une erreur est survenue lors de la mise à jour : " + str(e), "danger")

    return render_template('purchase/edit_purchase.html', form=form, purchase=purchase)

@bp.route('/delete/<int:purchase_id>', methods=['POST'])
@login_required
@staff_required
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)

    # Vérifier si des ventes ont été faites avec les médicaments de cet achat
    for item in purchase.items:
        drug = item.drug
        if not drug:
            continue
        # Vérifier si ce médicament a été vendu (quantité vendue > 0)
        total_sold = sum(sale_item.quantity for sale_item in drug.sales)
        if total_sold > 0:
            flash(
                f"Suppression impossible : le médicament '{drug.name}' a déjà été vendu.",
                "danger"
            )
            return redirect(url_for('purchase.list_purchases'))

    # Vérifier que la suppression ne causera pas de stock négatif
    problematic_items = []
    for item in purchase.items:
        drug = item.drug
        if drug is None:
            continue
        current_stock = drug.current_stock()
        if current_stock - item.quantity < 0:
            problematic_items.append((drug.name, current_stock, item.quantity))

    if problematic_items:
        msg = "Suppression impossible : stock insuffisant pour les médicaments suivants :\n"
        for name, stock, qty in problematic_items:
            msg += f"- {name} (stock actuel: {stock}, quantité à retirer: {qty})\n"
        flash(msg, "danger")
        return redirect(url_for('purchase.list_purchases'))

    # Si tout est OK, suppression
    try:
        db.session.delete(purchase)
        db.session.commit()
        flash('Achat supprimé avec succès.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash("Une erreur est survenue lors de la suppression. Veuillez réessayer.", "danger")
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
    days = int(request.args.get('days', 30))  # Par défaut 30 jours
    page = request.args.get('page', 1, type=int)
    per_page = 10  # items par page
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

    total = len(results)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_results = results[start:end]

    pagination = ManualPagination(paginated_results, page, per_page, total)

    return render_template(
        'purchase/purchase_stats_by_supplier.html',
        stats=pagination,
        selected_days=days
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