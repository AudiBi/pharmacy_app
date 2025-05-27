import pandas as pd
from flask import Blueprint, send_file
import io
from app.models import Sale

bp = Blueprint('report', __name__, url_prefix='/reports')

@bp.route('/export/sales/excel')
def export_sales_excel():
    sales = Sale.query.all()
    data = [{
        'ID': s.id,
        'Médicament': s.drug.name,
        'Quantité': s.quantity,
        'Date': s.date.strftime('%d/%m/%Y')
    } for s in sales]

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Ventes')

    output.seek(0)
    return send_file(output, as_attachment=True, download_name="ventes.xlsx")
