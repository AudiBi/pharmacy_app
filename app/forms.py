from flask_wtf import FlaskForm
from wtforms import DateTimeField, StringField, PasswordField, IntegerField, FloatField, SelectField, DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models import Supplier, Drug
from app import db

class LoginForm(FlaskForm):
    username = StringField('Nom d’utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])

class DrugForm(FlaskForm):
    name = StringField('Nom du médicament', validators=[DataRequired()])
    quantity = IntegerField('Quantité', validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField('Prix', validators=[DataRequired(), NumberRange(min=0)])
    unit = StringField('Unité', validators=[Optional(), Length(max=30)])
    expiration_date = DateField('Date d’expiration', validators=[DataRequired()])

class SupplierForm(FlaskForm):
    name = StringField('Nom du fournisseur', validators=[DataRequired()])
    contact = StringField('Contact', validators=[
        Optional(),
        Regexp(r'^[0-9+().\-\s]+$', message="Format de contact invalide")
    ])
    address = TextAreaField('Adresse', validators=[Optional()])

class SaleForm(FlaskForm):
    drug_id = SelectField('Médicament', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Quantité vendue', validators=[DataRequired(), NumberRange(min=1)])

class LossForm(FlaskForm):
    drug_id = SelectField('Médicament', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Quantité perdue', validators=[DataRequired(), NumberRange(min=1)])
    reason = SelectField('Raison', choices=[
        ('expiration', 'Périmé'),
        ('vol', 'Vol'),
        ('casse', 'Casse'),
        ('autre', 'Autre')
    ], validators=[DataRequired()])
    comment = TextAreaField('Commentaire', validators=[Optional()])

def supplier_choices():
    return db.session.query(Supplier).order_by(Supplier.name).all()

def drug_choices():
    return db.session.query(Drug).order_by(Drug.name).all()

class PurchaseForm(FlaskForm):
    supplier = QuerySelectField(
        'Fournisseur',
        query_factory=supplier_choices,
        get_label='name',
        allow_blank=False,
        validators=[DataRequired()]
    )
    drug = QuerySelectField(
        'Médicament',
        query_factory=drug_choices,
        get_label='name',
        allow_blank=False,
        validators=[DataRequired()]
    )
    quantity = IntegerField('Quantité', validators=[DataRequired(), NumberRange(min=1)])
    unit_price = FloatField('Prix unitaire', validators=[DataRequired(), NumberRange(min=0)])
    total_cost = FloatField('Coût total', validators=[Optional()])
    purchase_date = DateTimeField('Date d\'achat', format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    commentaire = TextAreaField('Commentaire', validators=[Optional()])
    submit = SubmitField('Enregistrer')

    def validate(self):
        rv = FlaskForm.validate(self)
        if not rv:
            return False
        # Calcul automatique du total_cost si absent
        if not self.total_cost.data and self.quantity.data and self.unit_price.data:
            self.total_cost.data = self.quantity.data * self.unit_price.data
        return True

