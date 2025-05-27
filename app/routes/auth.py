from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User
from app.forms import LoginForm
from app import db, login_manager

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_based_on_role(current_user)  # Redirection selon le rôle

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            if not user.is_active:
                flash('Compte désactivé. Contactez un administrateur.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user)
            flash('Connexion réussie !', 'success')
            return redirect_based_on_role(user)  # Redirection selon le rôle
        else:
            flash('Nom d’utilisateur ou mot de passe incorrect.', 'danger')

    return render_template('login.html', form=form)

# Fonction pour rediriger en fonction du rôle
def redirect_based_on_role(user):
    if user.role == 'admin':
        return redirect(url_for('dashboard.dashboard'))  # Tableau de bord pour admin
    elif user.role == 'employee':
        return redirect(url_for('dashboard.dashboard'))  # Tableau de bord pour employee
    else:
        flash("Rôle utilisateur inconnu", 'warning')
        return redirect(url_for('auth.login'))

@bp.route('/logout')
@login_required 
def logout():
    logout_user()  
    flash('Déconnexion réussie.', 'info')  
    return redirect(url_for('auth.login'))