import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student
    photo_url = db.Column(db.String(255), nullable=True)
    profile_image_type = db.Column(db.String(20), default='url') # 'url' or 'local'
    study_objective = db.Column(db.String(100), nullable=True)  # e.g., OAB, AWS
    search_intent = db.Column(db.Text, nullable=True) # "Qual o objetivo do estudo? O que busca?"
    is_approved = db.Column(db.Boolean, default=False)
    needs_password_change = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sessions = db.relationship('StudySession', backref='student', lazy=True)
    study_plans = db.relationship('StudyPlan', backref='student', lazy=True, foreign_keys='StudyPlan.student_id')
    certificates = db.relationship('Certificate', backref='student', lazy=True)
    mentorships_as_student = db.relationship('Mentorship', backref='student', lazy=True, foreign_keys='Mentorship.student_id')
    mentorships_as_teacher = db.relationship('Mentorship', backref='teacher', lazy=True, foreign_keys='Mentorship.teacher_id')
    submissions = db.relationship('Submission', backref='student', lazy=True)
    assigned_tasks = db.relationship('AssignedTask', backref='teacher', lazy=True, foreign_keys='AssignedTask.teacher_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

class AssignedTask(db.Model):
    __tablename__ = 'assigned_tasks'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # If null, it's for everyone or specific class logic
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    external_link = db.Column(db.String(255), nullable=True)
    attachment_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)

class License(db.Model):
    __tablename__ = 'licenses'
    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(50), unique=True, nullable=False)
    student_limit = db.Column(db.Integer, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<License {self.license_key}>'

class StudySession(db.Model):
    __tablename__ = 'study_sessions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('assigned_tasks.id'), nullable=True)
    subject = db.Column(db.String(100), nullable=False)
    subtitle = db.Column(db.String(100), nullable=True) # For hierarchy like AWS -> Lambda
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.utcnow().date())
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, default=0)
    type = db.Column(db.String(20), nullable=False)  # scheduled, free, assisted
    is_validated = db.Column(db.Boolean, default=False)
    
    # Completion details
    completion_comment = db.Column(db.Text, nullable=True)
    completion_file = db.Column(db.String(255), nullable=True)
    completion_link = db.Column(db.String(255), nullable=True)
    
    # Mentor Interaction
    mentor_feedback = db.Column(db.Text, nullable=True)
    mentor_feedback_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<StudySession {self.subject} - {self.duration_minutes}min>'

class StudyPlan(db.Model):
    __tablename__ = 'study_plans'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_subject = db.Column(db.String(100), nullable=False)
    target_hours = db.Column(db.Float, nullable=False)
    completed_hours = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active') # backlog, active, completed
    deadline = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<StudyPlan {self.target_subject}>'

class Mentorship(db.Model):
    __tablename__ = 'mentorships'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, active, rejected

    def __repr__(self):
        return f'<Mentorship S:{self.student_id} T:{self.teacher_id}>'

class Certificate(db.Model):
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    verification_code = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    total_hours = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_path = db.Column(db.String(255), nullable=True)
    
    # External tracking
    is_external = db.Column(db.Boolean, default=False)
    external_issuer = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Certificate {self.verification_code}>'

class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'file' or 'link'
    content = db.Column(db.String(255), nullable=False)  # filename or URL
    description = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Submission {self.type} - {self.content}>'

class SupportMessage(db.Model):
    __tablename__ = 'support_messages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to user
    user = db.relationship('User', backref=db.backref('support_messages', lazy=True))

    def __repr__(self):
        return f'<SupportMessage from {self.user_id}>'
