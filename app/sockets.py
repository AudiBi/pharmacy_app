import random
from datetime import datetime
from app import socketio

# Stockage en mémoire (exemple simple)
sales = []   # [(datetime, montant), ...]
alerts = []  # [str, ...]

LOW_STOCK_THRESHOLD = 5

def get_current_stock(drug_name):
    return random.randint(0, 10)  # simulation

def add_alert(msg):
    alerts.append(msg)
    socketio.emit('new_alert', {'message': msg})
