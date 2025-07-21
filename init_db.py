from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    confirm = input("⚠️  Attention, toutes les données vont être supprimées. Continuer ? (o/n) : ")
    if confirm.lower() != 'o':
        print("❌ Opération annulée.")
        exit()

    print("🔄 Réinitialisation de la base...")
    db.drop_all()
    db.create_all()

    # Liste des utilisateurs à créer
    default_users = [
        {"username": "admin", "password": "admin123", "role": "admin"},
        {"username": "pharma", "password": "pharma123", "role": "pharmacien"},
        {"username": "vendeur", "password": "vendeur123", "role": "vendeur"},
    ]

    for user_data in default_users:
        if not User.query.filter_by(username=user_data["username"]).first():
            user = User(
                username=user_data["username"],
                password=generate_password_hash(user_data["password"]),
                role=user_data["role"],
                is_active=True
            )
            db.session.add(user)
            print(f"✅ Utilisateur créé : {user.username} / {user_data['password']} ({user.role})")
        else:
            print(f"ℹ️  L'utilisateur {user_data['username']} existe déjà.")

    db.session.commit()
    print("✅ Base de données prête.")
