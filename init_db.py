from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    confirm = input(" Attention, toutes les données vont être supprimées. Continuer ? (o/n) : ")
    if confirm.lower() != 'o':
        print("Opération annulée.")
        exit()

    print("Réinitialisation de la base...")
    db.drop_all()
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password=generate_password_hash("admin123"),
            role="admin",
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin créé : admin / admin123")
    else:
        print("L'utilisateur admin existe déjà.")
