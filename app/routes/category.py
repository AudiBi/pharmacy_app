from io import BytesIO
from operator import or_
from flask import Blueprint, render_template, redirect, send_file, url_for, flash, abort, request
from flask_login import login_required, current_user
import pandas as pd
from app.forms import CategoryForm, DeleteCategoryForm
from app.models import Category
from app import db
from flask_paginate import Pagination, get_page_parameter

from app.routes.drug import admin_required
from app.routes.supplier import staff_required

bp = Blueprint('category', __name__, url_prefix='/categories')


@bp.route('/')
@login_required
@staff_required
def list_categories():
    search_query = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre de catégories par page

    # Filtrage conditionnel
    query = Category.query
    if search_query:
        query = query.filter(Category.name.ilike(f"%{search_query}%"))

    # Pagination
    pagination = query.order_by(Category.name.asc()).paginate(page=page, per_page=per_page)
    categories = pagination.items

    delete_form_category = DeleteCategoryForm()

    return render_template(
        'categories/list.html',
        categories=categories,
        pagination=pagination,
        search_query=search_query,
        delete_form_category=delete_form_category
    )

@bp.route('/categories/export_excel')
@login_required
def export_categories():
    search = request.args.get('search', '')

    query = Category.query
    if search:
        query = query.filter(Category.name.ilike(f"%{search}%"))

    categories = query.all()

    data = [{
        "ID": category.id,
        "Nom": category.name
    } for category in categories]

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Catégories')
    output.seek(0)

    return send_file(
        output,
        download_name='categories_medicaments.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        # Vérifier si la catégorie existe déjà (insensible à la casse si nécessaire)
        existing_category = Category.query.filter_by(name=form.name.data.strip()).first()
        if existing_category:
            flash("Cette catégorie existe déjà.", "warning")
            return render_template('categories/add.html', form=form)

        category = Category(name=form.name.data.strip())
        db.session.add(category)
        db.session.commit()
        flash("Catégorie ajoutée avec succès.", "success")
        return redirect(url_for('category.list_categories'))

    return render_template('categories/add.html', form=form)

@bp.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    form = CategoryForm(obj=category)

    if form.validate_on_submit():
        category.name = form.name.data
        db.session.commit()
        flash("Catégorie mise à jour avec succès.", "success")
        return redirect(url_for('category.list_categories'))

    return render_template('categories/edit.html', form=form)

@bp.route('/delete/<int:category_id>', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)

    if category.drugs:  # Vérifie s’il y a des médicaments liés
        flash("Impossible de supprimer : des médicaments sont liés à cette catégorie.", "danger")
        return redirect(url_for('category.list_categories'))

    db.session.delete(category)
    db.session.commit()
    flash("Catégorie supprimée avec succès.", "success")
    return redirect(url_for('category.list_categories'))
