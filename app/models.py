from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

### UTILISATEURS ###
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, pharmacien, vendeur...
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)

    sales = db.relationship('Sale', back_populates='user')

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)
    
    def mark_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()
        
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

    sales = db.relationship('SaleItem', back_populates='drug')
    losses = db.relationship('LossRecord', back_populates='drug')
    purchase_items = db.relationship('PurchaseItem', back_populates='drug')

    def is_expired(self):
        return self.expiration_date < date.today()

    def will_expire_soon(self, days=30):
        delta = self.expiration_date - date.today()
        return 0 <= delta.days <= days

    def current_stock(self):
        purchased = sum(item.quantity for item in self.purchase_items)
        sold = sum(s.net_quantity_sold for s in self.sales)
        lost = sum(l.quantity for l in self.losses)
        return purchased - sold - lost


### VENTES ###
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='sales')
    items = db.relationship('SaleItem', back_populates='sale', cascade='all, delete-orphan')

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items)
    
class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

    sale = db.relationship('Sale', back_populates='items')
    drug = db.relationship('Drug')

    @property
    def total_price(self):
        return self.quantity * self.unit_price
    
    @property
    def net_quantity_sold(self):
        returned_qty = sum(r.quantity for r in self.returns)
        return self.quantity - returned_qty

    
### PERTES ###
class LossRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    quantity = db.Column(db.Integer)
    reason = db.Column(db.String(50))  # périmé, cassé, volé...
    date = db.Column(db.DateTime, default=datetime.utcnow)
    comment = db.Column(db.Text)

    drug = db.relationship('Drug', back_populates='losses')

### ACHATS ###
class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    commentaire = db.Column(db.Text, nullable=True)

    supplier = db.relationship('Supplier', back_populates='purchases')
    items = db.relationship('PurchaseItem', back_populates='purchase', cascade='all, delete-orphan')

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items or [])

    @property
    def medications(self):
        return [item.drug.name for item in self.items if item.drug]

class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

    purchase = db.relationship('Purchase', back_populates='items')
    drug = db.relationship('Drug', back_populates='purchase_items')

    @property
    def total_price(self):
        return self.quantity * self.unit_price


class ReturnRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    refunded = db.Column(db.Boolean, default=True)  # Si un remboursement a été effectué

    sale_item = db.relationship('SaleItem', backref='returns')

    @property
    def amount(self):
        return self.quantity * self.sale_item.unit_price

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False, unique=True)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # espèces, mobile, carte, etc.
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

    sale = db.relationship('Sale', backref=db.backref('payment', uselist=False))