# routes/reports.py
from flask import Blueprint, render_template, request, flash
from flask_login import login_required
from datetime import datetime, date
from app.routes.drug import admin_required
from app.services.reporting import rapport_rentabilite

bp = Blueprint('report', __name__, url_prefix='/reports')


@bp.route('/rapport/rentabilite')
@login_required
@admin_required
def rentabilite_view():
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    # Par défaut, ne pas appeler la fonction si les dates ne sont pas fournies
    if not start_date or not end_date:
        # On affiche la page sans résultats (les variables sont None)
        return render_template(
            'rapport_rentabilite.html',
            start_date=start_date,
            end_date=end_date,
            total_ventes=None,
            total_achats=None,
            total_pertes=None,
            marge_brute=None,
        )

    # Sinon, calculer les valeurs du rapport
    rapport = rapport_rentabilite(start_date, end_date)

    return render_template(
        'rapport_rentabilite.html',
        start_date=start_date,
        end_date=end_date,
        total_ventes=rapport['total_ventes'],
        total_achats=rapport['total_achats'],
        total_pertes=rapport['total_pertes'],
        marge_brute=rapport['marge_brute'],
    )
