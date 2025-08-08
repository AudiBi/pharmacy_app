from datetime import datetime, timedelta
from io import BytesIO
from math import ceil
from flask import Blueprint, render_template, redirect, request, send_file, url_for, flash, abort
from flask_login import login_required, current_user
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import pandas as pd
from sqlalchemy import func
from app.decorators import admin_required, staff_required
from app.models import Drug, Payment, ReturnRecord, Sale, SaleItem, User
from app.forms import SaleForm, SaleItemForm
from sqlalchemy.exc import SQLAlchemyError
from app import db
from sqlalchemy.orm import joinedload


bp = Blueprint('sale', __name__, url_prefix='/sales')

def sales_stats_by_seller(days=7):
    since_date = datetime.utcnow() - timedelta(days=days)

    results = (
        db.session.query(
            User.username,
            func.count(Sale.id).label('nb_ventes'),
            func.coalesce(func.sum(SaleItem.quantity * SaleItem.unit_price), 0).label('ca_total')
        )
        .join(Sale, Sale.user_id == User.id)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .filter(Sale.date >= since_date)
        .group_by(User.id)
        .order_by(func.sum(SaleItem.quantity * SaleItem.unit_price).desc())
        .all()
    )

    return results

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

@bp.route('/export-sales')
def export_sales():
    search = request.args.get('search', '', type=str)
    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    user_id = request.args.get('user_id', type=int)

    query = Sale.query.options(joinedload(Sale.items).joinedload(SaleItem.drug), joinedload(Sale.user))

    if user_id:
        query = query.filter(Sale.user_id == user_id)

    if search:
        query = query.join(Sale.items).join(SaleItem.drug)
        query = query.filter(Drug.name.ilike(f"%{search}%"))

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Sale.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(Sale.date <= end)
        except ValueError:
            pass

    sales = query.order_by(Sale.date.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Ventes de médicaments"

    headers = [ "ID Vente", "Date", "Médicament", "Quantité", "Prix Unitaire", "Montant Total", "Vendu par"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for sale in sales:
        for item in sale.items:
            ws.append([
                sale.id,
                sale.date.strftime("%d/%m/%Y %H:%M"),
                item.drug.name,
                item.quantity,
                "%.2f" % item.unit_price,
                "%.2f" % (item.quantity * item.unit_price),
                sale.user.username
            ])

    # Ajustement des colonnes
    for col in ws.columns:
        max_length = max(len(str(cell.value)) for cell in col if cell.value is not None)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        download_name="ventes_medicaments.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/edit/<int:sale_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_sale(sale_id):
    # Récupérer la vente avec ses items
    sale = Sale.query.options(joinedload(Sale.items)).get_or_404(sale_id)

    form = SaleForm()
    drug_list = Drug.query.order_by(Drug.name).all()
    drug_choices = [(d.id, d.name) for d in drug_list]

    if request.method == 'GET':
        form.items.entries = []  # Vider la liste actuelle

        # Ajouter les produits existants
        for item in sale.items:
            form.items.append_entry({
                'drug_id': item.drug_id,
                'quantity': item.quantity
            })

        # Injecter les choix dans chaque sous-formulaire
        for subform in form.items:
            subform.form.drug_id.choices = drug_choices

        # Pré-remplir les données de paiement
        if sale.payment:
            form.payment_method.data = sale.payment.payment_method
            form.amount_paid.data = sale.payment.amount_paid
        else:
            form.payment_method.data = ''
            form.amount_paid.data = 0.0

        return render_template('sales/edit.html', form=form, sale=sale, drug_list=drug_list)

    # POST : injecter les choix dans tous les sous-formulaires AVANT la validation
    for subform in form.items:
        subform.form.drug_id.choices = drug_choices

    if form.validate_on_submit():
        try:
            # Supprimer les anciens items de vente
            SaleItem.query.filter_by(sale_id=sale.id).delete()

            new_items = []
            for item_form in form.items:
                drug_id = item_form.form.drug_id.data
                quantity = item_form.form.quantity.data
                drug = Drug.query.get(drug_id)

                if not drug:
                    raise Exception(f"Médicament avec ID {drug_id} introuvable.")

                if drug.current_stock() < quantity:
                    raise Exception(f"Stock insuffisant pour {drug.name}. Stock actuel : {drug.current_stock()}, demandé : {quantity}")

                new_item = SaleItem(
                    sale=sale,
                    drug_id=drug_id,
                    quantity=quantity,
                    unit_price=drug.price  # On stocke le prix actuel
                )
                new_items.append(new_item)

            # Mettre à jour ou créer le paiement
            if sale.payment:
                sale.payment.payment_method = form.payment_method.data
                sale.payment.amount_paid = form.amount_paid.data
                sale.payment.payment_date = sale.date
            else:
                new_payment = Payment(
                    sale=sale,
                    payment_method=form.payment_method.data,
                    amount_paid=form.amount_paid.data,
                    payment_date=sale.date
                )
                db.session.add(new_payment)

            # Ajouter les nouveaux items à la base
            db.session.add_all(new_items)
            db.session.commit()

            flash("Vente modifiée avec succès.", "success")
            return redirect(url_for('sale.sale_receipt', sale_id=sale.id))

        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Erreur lors de la modification : " + str(e), "danger")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")

    return render_template('sales/edit.html', form=form, sale=sale, drug_list=drug_list)
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

@bp.route('/return/<int:sale_id>', methods=['GET', 'POST'])
@staff_required
def return_items(sale_id):
    # Charger tous les items de la vente
    sale_items = SaleItem.query.options(joinedload(SaleItem.drug)).filter_by(sale_id=sale_id).all()

    if request.method == 'POST':
        any_returned = False  # Pour vérifier si un retour a été effectué

        for item in sale_items:
            try:
                qty_key = f'quantity_{item.id}'
                reason_key = f'reason_{item.id}'

                qty_returned = int(request.form.get(qty_key, 0))
                reason = request.form.get(reason_key, '').strip()

                # Ignore les quantités nulles ou négatives
                if qty_returned <= 0:
                    continue

                if qty_returned > item.net_quantity_sold:
                    flash(f"Quantité retournée pour {item.drug.name} dépasse la quantité vendue restante.", "danger")
                    continue

                # Créer l’enregistrement du retour
                return_record = ReturnRecord(
                    sale_item_id=item.id,
                    quantity=qty_returned,
                    reason=reason
                )
                db.session.add(return_record)
                any_returned = True

            except (ValueError, TypeError):
                flash(f"Quantité invalide pour {item.drug.name}.", "danger")
                continue

        if any_returned:
            db.session.commit()
            flash("Retour(s) enregistré(s) avec succès.", "success")
        else:
            flash("Aucun retour n’a été effectué.", "warning")

        return redirect(url_for('sale.return_receipt', sale_id=sale_id))

    return render_template('sales/return_item.html', sale_items=sale_items)

@bp.route('/returns')
@login_required
@staff_required
def list_returns():
    # Récupération des paramètres de filtre
    drug_id = request.args.get('drug_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre de catégories par page

    # Base query
    query = ReturnRecord.query.join(ReturnRecord.sale_item).join(SaleItem.drug)

    # Filtrer par médicament
    if drug_id:
        query = query.filter(SaleItem.drug_id == drug_id)

    # Filtrer par dates
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(ReturnRecord.date >= start_date)
        except ValueError:
            pass  # Format de date invalide ignoré

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Ajouter une journée complète à la date de fin
            end_date = end_date.replace(hour=23, minute=59, second=59)
            query = query.filter(ReturnRecord.date <= end_date)
        except ValueError:
            pass

    # Pagination
    pagination = query.order_by(ReturnRecord.date.desc()).paginate(page=page, per_page=per_page)
    returns = pagination.items

    # Liste des médicaments pour le filtre
    drugs = Drug.query.order_by(Drug.name).all()

    return render_template(
        'sales/returns.html',
        returns=returns,
        pagination=pagination,
        drugs=drugs,
        selected_drug_id=drug_id,
        start_date=start_date_str,
        end_date=end_date_str
    )

@bp.route('/returns/export')
@staff_required
def export_returns():
    # Récupération des filtres GET
    drug_id = request.args.get('drug_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    refunded = request.args.get('refunded')  # Pas dans le template actuel, mais prêt si ajouté plus tard

    # Construction de la requête
    query = ReturnRecord.query.join(SaleItem).join(Drug)

    if drug_id:
        query = query.filter(SaleItem.drug_id == drug_id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(ReturnRecord.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(ReturnRecord.date <= end)
        except ValueError:
            pass

    if refunded == 'yes':
        query = query.filter(ReturnRecord.refunded.is_(True))
    elif refunded == 'no':
        query = query.filter(ReturnRecord.refunded.is_(False))

    returns = query.order_by(ReturnRecord.date.desc()).all()

    # Construction du DataFrame
    data = []
    for ret in returns:
        drug = ret.sale_item.drug
        sale = ret.sale_item.sale

        data.append({
            'Date': ret.date.strftime('%d/%m/%Y %H:%M'),
            'Médicament': drug.name if drug else "Inconnu",
            'Vente #': sale.id if sale else "N/A",
            'Qté retournée': ret.quantity,
            'Montant remboursé (HTG)': round(ret.amount, 2),
            'Raison': ret.reason or "-",
            'Remboursé': "Oui" if ret.refunded else "Non"
        })

    df = pd.DataFrame(data)

    # Export en mémoire
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Retours")
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="retours_medicaments.xlsx"
    )

@bp.route('/return-receipt/<int:sale_id>')
@staff_required
def return_receipt(sale_id):
    # Rechercher tous les retours associés à la vente
    return_records = ReturnRecord.query.options(
        joinedload(ReturnRecord.sale_item).joinedload(SaleItem.drug),
        joinedload(ReturnRecord.sale_item).joinedload(SaleItem.sale)
    ).all()

    # Filtrer manuellement les retours qui appartiennent à la vente souhaitée
    return_records = [r for r in return_records if r.sale_item and r.sale_item.sale_id == sale_id]

    if not return_records:
        flash("Aucun retour trouvé pour cette vente.", "warning")
        return redirect(url_for("sale.list_returns"))

    total_returned = sum(record.amount for record in return_records)

    return render_template(
        'sales/return_receipt.html',
        return_records=return_records,
        total_returned=total_returned
    )

@bp.route('/sales_by_seller')
@admin_required
def sales_by_seller():
    days = int(request.args.get('days', 7))  # Nombre de jours sélectionnés
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre d'éléments par page

    # Toutes les statistiques (liste de vendeurs + stats)
    all_stats = sales_stats_by_seller(days)
    total = len(all_stats)

    # Pagination manuelle
    start = (page - 1) * per_page
    end = start + per_page
    stats_paginated = all_stats[start:end]

    # Simuler un objet de pagination comme avec paginate()
    class ManualPagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = ceil(total / per_page)
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

    stats = ManualPagination(stats_paginated, page, per_page, total)

    return render_template(
        'sales/sales_by_seller.html',
        stats=stats,
        selected_days=days
    )