from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User
from app.forms import LoginForm, PasswordChangeForm
from app import db, login_manager

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Rediriger si déjà connecté
    if current_user.is_authenticated:
        return redirect_based_on_role(current_user)

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if not user:
            flash('Nom d’utilisateur ou mot de passe incorrect.', 'danger')
            return render_template('login.html', form=form)

        if not user.is_active:
            flash('Compte désactivé. Contactez un administrateur.', 'warning')
            return render_template('login.html', form=form)

        if check_password_hash(user.password, form.password.data):
            login_user(user)
            user.mark_login() 
            user.last_login = datetime.utcnow()  # Facultatif : mise à jour du dernier accès
            db.session.commit()
            flash('Connexion réussie !', 'success')
            return redirect_based_on_role(user)

        flash('Nom d’utilisateur ou mot de passe incorrect.', 'danger')

    return render_template('login.html', form=form)

def redirect_based_on_role(user):
    roles_valides = ['admin', 'pharmacien', 'vendeur']
    if user.role in roles_valides:
        return redirect(url_for('dashboard.dashboard'))
    else:
        flash("Rôle utilisateur inconnu", 'warning')
        return redirect(url_for('auth.login'))

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = PasswordChangeForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Mot de passe actuel incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Votre mot de passe a été modifié avec succès.", "success")
            return redirect(url_for('dashboard.dashboard'))

    return render_template("users/change_password.html", form=form)