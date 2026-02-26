from main import app
from models import db

with app.app_context():
    # create_all only creates tables that don't exist yet, it won't drop existing ones
    db.create_all()
    print("Database tables ensured.")
