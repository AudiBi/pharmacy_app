from . import db
from flask_login import UserMixin
from datetime import datetime, date

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(15))  # prévoir regex dans validation formulaire
    address = db.Column(db.Text)

    purchases = db.relationship('Purchase', back_populates='supplier')

class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(30))  # ex: comprimé, flacon
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    commentaire = db.Column(db.Text, nullable=True)

    sales = db.relationship('Sale', back_populates='drug')
    losses = db.relationship('LossRecord', back_populates='drug')
    purchases = db.relationship('Purchase', back_populates='drug')

    def is_expired(self):
        return self.expiration_date < date.today()

    def will_expire_soon(self, days=30):
        delta = self.expiration_date - date.today()
        return 0 <= delta.days <= days

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    quantity = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    drug = db.relationship('Drug', back_populates='sales')

class LossRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    quantity = db.Column(db.Integer)
    reason = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    drug = db.relationship('Drug', back_populates='losses')

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    quantity = db.Column(db.Integer)
    unit_price = db.Column(db.Float)   # prix unitaire
    total_cost = db.Column(db.Float)   # total achat
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    commentaire = db.Column(db.Text, nullable=True)

    supplier = db.relationship('Supplier', back_populates='purchases')
    drug = db.relationship('Drug', back_populates='purchases')
