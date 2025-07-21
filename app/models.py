from . import db
from flask_login import UserMixin
from datetime import datetime, date

### UTILISATEURS ###
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, pharmacien, vendeur...
    is_active = db.Column(db.Boolean, default=True)

    sales = db.relationship('Sale', back_populates='user')

### FOURNISSEURS ###
class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(15))
    address = db.Column(db.Text)

    purchases = db.relationship('Purchase', back_populates='supplier')

### CATÉGORIES DE MÉDICAMENTS (OPTIONNEL MAIS UTILE) ###
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    drugs = db.relationship('Drug', back_populates='category')

### MÉDICAMENTS ###
class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(30))  # comprimé, flacon, etc.
    price = db.Column(db.Float, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    commentaire = db.Column(db.Text, nullable=True)

    # Liens
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', back_populates='drugs')

    sales = db.relationship('Sale', back_populates='drug')
    losses = db.relationship('LossRecord', back_populates='drug')
    purchases = db.relationship('Purchase', back_populates='drug')

    def is_expired(self):
        return self.expiration_date < date.today()

    def will_expire_soon(self, days=30):
        delta = self.expiration_date - date.today()
        return 0 <= delta.days <= days

    def current_stock(self):
        purchased = sum(p.quantity for p in self.purchases)
        sold = sum(s.quantity for s in self.sales)
        lost = sum(l.quantity for l in self.losses)
        return purchased - sold - lost

### VENTES ###
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Qui a fait la vente
    quantity = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    drug = db.relationship('Drug', back_populates='sales')
    user = db.relationship('User', back_populates='sales')

### PERTES ###
class LossRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    quantity = db.Column(db.Integer)
    reason = db.Column(db.String(50))  # périmé, cassé, volé...
    date = db.Column(db.DateTime, default=datetime.utcnow)

    drug = db.relationship('Drug', back_populates='losses')

### ACHATS ###
class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    quantity = db.Column(db.Integer)
    unit_price = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    commentaire = db.Column(db.Text, nullable=True)

    supplier = db.relationship('Supplier', back_populates='purchases')
    drug = db.relationship('Drug', back_populates='purchases')
