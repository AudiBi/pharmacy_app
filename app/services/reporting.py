from sqlalchemy import func, and_
from app.models import LossRecord, PurchaseItem, Sale, SaleItem
from app import db
from datetime import datetime


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def rapport_rentabilite(start_date, end_date):
    start_date = parse_date(start_date) if isinstance(start_date, str) else start_date
    end_date = parse_date(end_date) if isinstance(end_date, str) else end_date

    if not start_date or not end_date:
        return {
            'total_ventes': 0.0,
            'total_achats': 0.0,
            'total_pertes': 0.0,
            'marge_brute': 0.0,
            'marge_percent': 0.0
        }

    total_ventes = db.session.query(
        func.sum(SaleItem.quantity * SaleItem.unit_price)
    ).join(Sale).filter(
        and_(Sale.date >= start_date, Sale.date <= end_date)
    ).scalar() or 0

    drug_ids_vendus = [d[0] for d in db.session.query(
        SaleItem.drug_id
    ).join(Sale).filter(
        and_(Sale.date >= start_date, Sale.date <= end_date)
    ).distinct().all()]

    total_achats = db.session.query(
        func.sum(PurchaseItem.quantity * PurchaseItem.unit_price)
    ).filter(PurchaseItem.drug_id.in_(drug_ids_vendus)).scalar() or 0

    pertes = db.session.query(LossRecord).filter(
        and_(LossRecord.date >= start_date, LossRecord.date <= end_date)
    ).all()

    prix_moyens = dict(
        db.session.query(
            PurchaseItem.drug_id,
            func.avg(PurchaseItem.unit_price)
        ).group_by(PurchaseItem.drug_id).all()
    )

    total_pertes = sum([
        perte.quantity * prix_moyens.get(perte.drug_id, 0)
        for perte in pertes
    ])

    marge_brute = total_ventes - total_achats - total_pertes
    marge_percent = (marge_brute / total_ventes * 100) if total_ventes > 0 else 0

    return {
        'total_ventes': round(total_ventes, 2),
        'total_achats': round(total_achats, 2),
        'total_pertes': round(total_pertes, 2),
        'marge_brute': round(marge_brute, 2),
        'marge_percent': round(marge_percent, 2)
    }
