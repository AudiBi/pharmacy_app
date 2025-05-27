from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from datetime import datetime

# Initialisation des extensions à l'échelle du module (global)
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = 'auth.login'

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Initialisation des extensions avec l'app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Context processor global (exemple : injecter current_year)
    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    # Import des blueprints à l’intérieur de create_app pour éviter boucle
    from app.routes import auth, drug, supplier, sale, stock_routes, dashboard, history, purchase

    app.register_blueprint(auth.bp)
    app.register_blueprint(drug.bp)
    app.register_blueprint(supplier.bp)
    app.register_blueprint(sale.bp)
    app.register_blueprint(stock_routes.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(purchase.bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    return app
