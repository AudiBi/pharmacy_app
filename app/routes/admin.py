from io import BytesIO
from flask import Blueprint, render_template, redirect, send_file, url_for, flash, request
import pandas as pd
from app.forms import DeleteUserForm, PasswordChangeForm, UserForm
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import current_user, login_required
from app.decorators import role_required
from app import db
from app.routes.drug import admin_required

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_user():
    form = UserForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash(f"L'utilisateur '{form.username.data}' existe déjà.", "warning")
            return render_template('admin/create_user.html', form=form)

        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            password=hashed_password,
            role=form.role.data,
            is_active=form.is_active.data
        )
        db.session.add(user)
        db.session.commit()
        flash("Utilisateur créé avec succès", "success")
        return redirect(url_for('admin.list_users'))
    return render_template('admin/create_user.html', form=form)

@bp.route('/admin/users')
@login_required
@role_required('admin')
def list_users():
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')

    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre de catégories par page

    query = User.query

    if search:
        query = query.filter(User.username.ilike(f"%{search}%"))
    if role_filter:
        query = query.filter_by(role=role_filter)

    # Pagination
    pagination = query.order_by(User.id).paginate(page=page, per_page=per_page)
    users = pagination.items

    delete_form = DeleteUserForm()  
    
    return render_template('admin/user_list.html', users=users, pagination=pagination, search=search, role_filter=role_filter, delete_form=delete_form)

@bp.route('/admin/export-users')
def export_users():
    search = request.args.get('search', '', type=str).lower()
    role = request.args.get('role', '', type=str)

    # Filtrage dynamique
    query = User.query
    if search:
        query = query.filter(User.username.ilike(f'%{search}%'))
    if role:
        query = query.filter(User.role == role)

    users = query.order_by(User.id).all()

    # Transformation en DataFrame
    user_data = [{
        "ID": user.id,
        "Nom d’utilisateur": user.username,
        "Rôle": user.role.capitalize(),
        "Actif": "Oui" if user.is_active else "Non"
    } for user in users]

    df = pd.DataFrame(user_data)

    # Création fichier Excel en mémoire
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Utilisateurs')
    output.seek(0)

    # Envoi du fichier en pièce jointe
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='utilisateurs.xlsx'
    )

@bp.route('/admin/user/<int:user_id>/toggle')
@login_required
@role_required('admin')
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f"Statut de l'utilisateur {user.username} mis à jour.", "info")
    return redirect(url_for('admin.list_users'))

@bp.route('/changer_mot_de_passe', methods=['GET', 'POST'])
@login_required
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not check_password_hash(current_user.password, form.current_password.data):
            flash("Mot de passe actuel incorrect.", "danger")
        else:
            current_user.password = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash("Mot de passe mis à jour avec succès.", "success")
            return redirect(url_for('dashboard'))

    return render_template('users/change_password.html', form=form)

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)  # préremplit avec user

    if form.validate_on_submit():
        user.username = form.username.data
        user.role = form.role.data
        user.is_active = form.is_active.data

        # Mise à jour du mot de passe uniquement si le champ n'est pas vide
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data)

        db.session.commit()
        flash(f"L'utilisateur {user.username} a été modifié avec succès.", "success")
        return redirect(url_for('admin.list_users'))

    return render_template('admin/edit_user.html', form=form, user=user)

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for('admin.list_users'))

    db.session.delete(user)
    db.session.commit()
    flash(f"L'utilisateur {user.username} a été supprimé avec succès.", "success")
    return redirect(url_for('admin.list_users'))