from app import create_app, db
from app.models import User, Supplier, Category, Drug, Purchase, PurchaseItem
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    confirm = input("⚠️  Attention, toutes les données vont être supprimées. Continuer ? (o/n) : ")
    if confirm.lower() != 'o':
        print("❌ Opération annulée.")
        exit()

    print("🔄 Réinitialisation de la base...")
    db.drop_all()
    db.create_all()

    ### Utilisateurs ###
    users = [
        {"username": "admin", "password": "admin123", "role": "admin"},
        {"username": "pharma", "password": "pharma123", "role": "pharmacien"},
        {"username": "vendeur", "password": "vendeur123", "role": "vendeur"},
    ]

    for u in users:
        user = User(
            username=u["username"],
            password=generate_password_hash(u["password"]),
            role=u["role"],
            is_active=True
        )
        db.session.add(user)

    ### Fournisseurs ###
    suppliers = [
        Supplier(name="Pharma Haiti", contact="50912345678", address="Port-au-Prince"),
        Supplier(name="MediPlus", contact="50987654321", address="Cap-Haïtien")
    ]
    db.session.add_all(suppliers)

    ### Catégories ###
    categories = [
        Category(name="Antibiotiques"),
        Category(name="Antalgiques"),
        Category(name="Vitamines")
    ]
    db.session.add_all(categories)
    db.session.flush()  # pour récupérer les IDs

    ### Médicaments ###
    drugs = [
        Drug(
            name="Amoxicilline",
            unit="gélule",
            price=25.0,
            expiration_date=datetime.now().date() + timedelta(days=365),
            category_id=categories[0].id
        ),
        Drug(
            name="Paracétamol",
            unit="comprimé",
            price=10.0,
            expiration_date=datetime.now().date() + timedelta(days=180),
            category_id=categories[1].id
        ),
        Drug(
            name="Vitamine C",
            unit="flacon",
            price=15.5,
            expiration_date=datetime.now().date() + timedelta(days=90),
            category_id=categories[2].id
        )
    ]
    db.session.add_all(drugs)
    db.session.flush()

    ### Achats et items ###
    purchase1 = Purchase(
        supplier_id=suppliers[0].id,
        purchase_date=datetime.now(),
        commentaire="Premier achat"
    )
    purchase1.items = [
        PurchaseItem(drug_id=drugs[0].id, quantity=100, unit_price=24.0),
        PurchaseItem(drug_id=drugs[1].id, quantity=200, unit_price=9.5)
    ]

    purchase2 = Purchase(
        supplier_id=suppliers[1].id,
        purchase_date=datetime.now(),
        commentaire="Deuxième livraison"
    )
    purchase2.items = [
        PurchaseItem(drug_id=drugs[2].id, quantity=150, unit_price=14.5)
    ]

    db.session.add_all([purchase1, purchase2])

    ### Commit final ###
    db.session.commit()

    print("✅ Base de données initialisée avec succès.")
