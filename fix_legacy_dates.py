import os
from datetime import timedelta
from main import app, db
from models import StudySession

def fix_legacy_dates():
    with app.app_context():
        # Get all legacy sessions
        legacy_sessions = StudySession.query.filter_by(
            subtitle="Carga Horária Legada"
        ).all()
        
        count = 0
        for session in legacy_sessions:
            # Shift everything back by 24 hours to ensure they don't count for "today"
            if session.start_time:
                session.start_time -= timedelta(hours=24)
            if session.end_time:
                session.end_time -= timedelta(hours=24)
            if session.date:
                # date object
                session.date -= timedelta(days=1)
            count += 1
            
        db.session.commit()
        print(f"Sucesso! {count} sessões legadas foram movidas 24h para o passado.")

if __name__ == "__main__":
    fix_legacy_dates()
