from flask_mail import Message
from app import mail
from flask import current_app

def envoyer_alerte_stock(drug_name, destinataire):
    msg = Message(
        subject=f"[Alerte] Rupture de stock : {drug_name}",
        recipients=[destinataire],
        body=f"⚠️ Le médicament '{drug_name}' est en rupture de stock. Merci d’agir rapidement.",
    )
    mail.send(msg)
