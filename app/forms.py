from flask_wtf import FlaskForm
from wtforms import DateTimeField, DecimalField, FieldList, FormField, StringField, PasswordField, IntegerField, FloatField, SelectField, DateField, SubmitField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp, InputRequired, EqualTo
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models import Supplier, Drug
from app import db

class LoginForm(FlaskForm):
    username = StringField('Nom d’utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
class UserForm(FlaskForm):
    username = StringField('Nom d’utilisateur', validators=[InputRequired(), Length(min=3, max=80)])
    password = PasswordField('Mot de passe', validators=[InputRequired(), Length(min=6)])
    role = SelectField('Rôle', choices=[('admin', 'Admin'), ('pharmacien', 'Pharmacien'), ('vendeur', 'Vendeur')])
    is_active = BooleanField('Actif', default=True)
    submit = SubmitField('Enregistrer')
class DeleteUserForm(FlaskForm):
    pass
class PasswordChangeForm(FlaskForm):
    current_password = PasswordField("Mot de passe actuel", validators=[InputRequired()])
    new_password = PasswordField("Nouveau mot de passe", validators=[
        InputRequired(),
        Length(min=6),
        EqualTo('confirm_password', message="Les mots de passe ne correspondent pas.")
    ])
    confirm_password = PasswordField("Confirmer le nouveau mot de passe", validators=[InputRequired()])
    submit = SubmitField("Changer le mot de passe")
class DrugForm(FlaskForm):
    name = StringField('Nom du médicament', validators=[DataRequired()])
    price = FloatField('Prix', validators=[DataRequired(), NumberRange(min=0)])
    unit = StringField('Unité', validators=[Optional(), Length(max=30)])
    expiration_date = DateField('Date d’expiration', validators=[DataRequired()])

    category = SelectField('Catégorie', coerce=int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Category
        self.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
        self.category.choices.insert(0, (0, '— Aucune —'))

class DeleteDrugForm(FlaskForm):
    pass

class LossForm(FlaskForm):
    drug_id = SelectField('Médicament', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Quantité', validators=[DataRequired(), NumberRange(min=1)])
    reason = StringField('Raison', validators=[DataRequired()])
    submit = SubmitField('Enregistrer perte')
class SupplierForm(FlaskForm):
    name = StringField(
        'Nom du fournisseur',
        validators=[
            DataRequired(message="Le nom est obligatoire."),
            Length(max=100, message="Le nom ne peut pas dépasser 100 caractères.")
        ]
    )

    contact = StringField(
        'Contact',
        validators=[
            Optional(),
            Regexp(
                r'^[0-9+().\-\s]{5,15}$',
                message="Le contact doit contenir entre 5 et 15 caractères valides (chiffres, +, -, etc.)"
            )
        ]
    )

    address = TextAreaField(
        'Adresse',
        validators=[
            Optional(),
            Length(max=300, message="L'adresse ne peut pas dépasser 300 caractères.")
        ]
    )
class DeleteSupplierForm(FlaskForm):
    pass

class SaleItemForm(FlaskForm):
    class Meta:
        csrf = False  # Désactive CSRF pour les sous-formulaires

    drug_id = SelectField("Médicament", coerce=int, validators=[DataRequired()])
    quantity = IntegerField("Quantité", validators=[DataRequired(), NumberRange(min=1)])
class SaleForm(FlaskForm):
       items = FieldList(FormField(SaleItemForm), min_entries=1)
       payment_method = SelectField("Mode de paiement", choices=[
            ('espèces', 'Espèces'),
            ('mobile', 'Mobile Money'),
            ('carte', 'Carte bancaire'),
        ], validators=[InputRequired()])
    
       amount_paid = FloatField("Montant payé", validators=[InputRequired(), NumberRange(min=0)])
       submit = SubmitField("Enregistrer la vente")

class DeleteSaleForm(FlaskForm):
    pass
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
    submit = SubmitField('Enregistrer')  

def supplier_choices():
    return db.session.query(Supplier).order_by(Supplier.name).all()

def drug_choices():
    return db.session.query(Drug).order_by(Drug.name).all()

class DeleteLostForm(FlaskForm):
    pass

class PurchaseItemForm(FlaskForm):
    class Meta:
        csrf = False  # Désactive CSRF pour les sous-formulaires
        
    drug_id = SelectField('Médicament', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Quantité', validators=[DataRequired(), NumberRange(min=1)])
    unit_price = DecimalField('Prix unitaire', validators=[DataRequired(), NumberRange(min=0)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drug_id.choices = [(drug.id, f"{drug.name} ({drug.category.name if drug.category else 'Sans catégorie'})") 
                                for drug in Drug.query.order_by(Drug.name).all()]

class PurchaseForm(FlaskForm):
    supplier = SelectField('Fournisseur', coerce=int, validators=[DataRequired()])
    purchase_date = DateField('Date d\'achat', validators=[Optional()])
    commentaire = TextAreaField('Commentaire', validators=[Optional()])

    items = FieldList(FormField(PurchaseItemForm), min_entries=1, max_entries=20)

    submit = SubmitField('Enregistrer')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.supplier.choices = [(supplier.id, supplier.name) for supplier in Supplier.query.order_by(Supplier.name).all()]

class CategoryForm(FlaskForm):
    name = StringField("Nom de la catégorie", validators=[DataRequired()])
    submit = SubmitField("Enregistrer")

class DeleteCategoryForm(FlaskForm):
    pass