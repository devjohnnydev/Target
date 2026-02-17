import os
from main import app, db, User, StudySession, StudyPlan, Mentorship

def test_student_dashboard_logic():
    with app.app_context():
        # Create a test student
        test_user = User(name="Test Student", email="test@student.com", role="student", is_approved=True)
        test_user.set_password("password")
        db.session.add(test_user)
        db.session.commit()
        
        # Simulate student_dashboard logic
        sessions = StudySession.query.filter_by(student_id=test_user.id).all()
        plans = StudyPlan.query.filter_by(student_id=test_user.id).all()
        total_minutes = sum(s.duration_minutes for s in sessions if s.duration_minutes)
        total_hours = round(total_minutes / 60, 1)
        
        print(f"Total Hours: {total_hours}")
        print("Success!")

try:
    if os.path.exists('target.db'):
        os.remove('target.db')
    test_student_dashboard_logic()
except Exception as e:
    print(f"Error caught: {e}")
