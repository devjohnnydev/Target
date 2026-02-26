import os
from datetime import datetime
from main import app, db
from models import User, StudySession

def check_legacy_dates():
    with app.app_context():
        # Get users
        names = ["Maria Eduarda", "Guilherme", "Lucas"]
        for name in names:
            user = User.query.filter(User.name.ilike(f"%{name}%")).first()
            if not user:
                continue
            
            # Get legacy sessions (subtitle="Carga Horária Legada")
            legacy_sessions = StudySession.query.filter_by(
                student_id=user.id, 
                subtitle="Carga Horária Legada"
            ).order_by(StudySession.start_time.desc()).all()
            
            if legacy_sessions:
                print(f"\n{user.name}: {len(legacy_sessions)} legacy sessions.")
                print(f"  Most recent: Date={legacy_sessions[0].date}, Start={legacy_sessions[0].start_time}")
                print(f"  Oldest: Date={legacy_sessions[-1].date}, Start={legacy_sessions[-1].start_time}")
                
            # Check today's sessions
            today = datetime.utcnow().date()
            today_sessions = StudySession.query.filter_by(
                student_id=user.id,
                date=today
            ).all()
            
            today_mins = sum(s.duration_minutes for s in today_sessions if s.duration_minutes)
            print(f"  Today real sessions: {len([s for s in today_sessions if s.subtitle != 'Carga Horária Legada'])}, Todays legacy: {len([s for s in today_sessions if s.subtitle == 'Carga Horária Legada'])}")
            print(f"  Total Today Mins: {today_mins}")

if __name__ == "__main__":
    check_legacy_dates()
