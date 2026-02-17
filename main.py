import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, License, StudySession, StudyPlan, Mentorship, Certificate, Submission
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'target-saas-secret-key'

# Railway / Production Database Configuration
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///target.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'zip', 'doc', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/certificates', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Role required decorator
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role != role:
                flash('Acesso negado: você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('dashboard'))
            if not current_user.is_approved and request.endpoint != 'waiting':
                return redirect(url_for('waiting'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Basic Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    return redirect(url_for('student_dashboard'))

# --- Admin Routes ---

@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    users = User.query.all()
    total_hours = db.session.query(db.func.sum(StudySession.duration_minutes)).scalar() or 0
    total_hours = round(total_hours / 60, 1)
    licenses = License.query.all()
    return render_template('admin/dashboard.html', users=users, total_hours=total_hours, licenses=licenses)

@app.route('/admin/approve/<int:user_id>')
@role_required('admin')
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'Usuário {user.name} aprovado com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    # Requisito do usuário: senha padrão "target"
    user.set_password('target')
    user.needs_password_change = True
    db.session.commit()
    flash(f'Senha de {user.name} resetada para "target". O usuário deverá trocar a senha no próximo acesso.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/license/create', methods=['POST'])
@role_required('admin')
def create_license():
    key = str(uuid.uuid4())[:8].upper()
    limit = int(request.form.get('limit', 10))
    # For simplicity, license valid for 1 year
    from datetime import timedelta
    valid_until = datetime.utcnow() + timedelta(days=365)
    
    new_license = License(license_key=key, student_limit=limit, valid_until=valid_until)
    db.session.add(new_license)
    db.session.commit()
    flash(f'Licença {key} criada com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/monitoring')
@role_required('admin')
def admin_monitoring():
    # Get active sessions (end_time is None)
    active_sessions = StudySession.query.filter_by(end_time=None).all()
    return render_template('admin/monitoring.html', active_sessions=active_sessions)

# --- Teacher Routes ---

@app.route('/teacher')
@role_required('teacher')
def teacher_dashboard():
    # Show students linked to this teacher via Mentorship
    mentorships = Mentorship.query.filter_by(teacher_id=current_user.id, status='active').all()
    students = [m.student for m in mentorships]
    return render_template('teacher/dashboard.html', students=students)

@app.route('/teacher/plan/create', methods=['POST'])
@role_required('teacher')
def create_study_plan():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    hours = float(request.form.get('hours'))
    
    new_plan = StudyPlan(student_id=student_id, mentor_id=current_user.id, target_subject=subject, target_hours=hours)
    db.session.add(new_plan)
    db.session.commit()
    flash('Plano de estudo criado com sucesso!', 'success')
    return redirect(url_for('teacher_dashboard'))

# --- Student Routes ---

@app.route('/student')
@role_required('student')
def student_dashboard():
    sessions = StudySession.query.filter_by(student_id=current_user.id).order_by(StudySession.start_time.desc()).all()
    plans = StudyPlan.query.filter_by(student_id=current_user.id).all()
    total_minutes = sum(s.duration_minutes for s in sessions if s.duration_minutes)
    total_hours = round(total_minutes / 60, 1)
    all_teachers = User.query.filter_by(role='teacher', is_approved=True).all()
    return render_template('student/dashboard.html', sessions=sessions, plans=plans, total_hours=total_hours, all_teachers=all_teachers)

@app.route('/study/log', methods=['POST'])
@role_required('student')
def log_study():
    subject = request.form.get('subject')
    minutes = int(request.form.get('minutes'))
    
    # Simple manual log for now
    new_session = StudySession(
        student_id=current_user.id,
        subject=subject,
        start_time=datetime.utcnow(),
        duration_minutes=minutes,
        type='free',
        is_validated=True # Manual for now
    )
    db.session.add(new_session)
    db.session.commit()
    flash('Hora de estudo registrada!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/certificate/generate')
@role_required('student')
def generate_cert():
    sessions = StudySession.query.filter_by(student_id=current_user.id).all()
    total_minutes = sum(s.duration_minutes for s in sessions if s.duration_minutes)
    total_hours = round(total_minutes / 60, 1)
    
    if total_hours < 1:
        flash('Você precisa de pelo menos 1 hora de estudo para gerar um certificado.', 'warning')
        return redirect(url_for('student_dashboard'))
    
    from utils import generate_study_certificate
    v_code = str(uuid.uuid4())
    pdf_path = generate_study_certificate(current_user.name, total_hours, v_code, current_user.study_objective)
    
    cert = Certificate(student_id=current_user.id, verification_code=v_code, total_hours=total_hours, pdf_path=pdf_path)
    db.session.add(cert)
    db.session.commit()
    
    flash('Certificado gerado com sucesso!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/study/submit-file', methods=['POST'])
@role_required('student')
def submit_file():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    file = request.files['file']
    description = request.form.get('description')
    
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    if file and allowed_file(file.filename):
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        # Unique mapping: user_id + timestamp + filename
        unique_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        new_submission = Submission(
            student_id=current_user.id,
            type='file',
            content=unique_filename,
            description=description
        )
        db.session.add(new_submission)
        db.session.commit()
        flash('Arquivo enviado com sucesso!', 'success')
    else:
        flash('Tipo de arquivo não permitido.', 'danger')
        
    return redirect(url_for('student_dashboard'))

@app.route('/study/submit-link', methods=['POST'])
@role_required('student')
def submit_link():
    link = request.form.get('link')
    description = request.form.get('description')
    
    if not link:
        flash('O link é obrigatório.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    new_submission = Submission(
        student_id=current_user.id,
        type='link',
        content=link,
        description=description
    )
    db.session.add(new_submission)
    db.session.commit()
    flash('Link salvo com sucesso!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/certificates/<filename>')
@login_required
def download_certificate(filename):
    return send_from_directory('static/certificates', filename)

@app.route('/mentorship/request', methods=['POST'])
@role_required('student')
def request_mentorship():
    teacher_id = request.form.get('teacher_id')
    # Check if already exists
    exists = Mentorship.query.filter_by(student_id=current_user.id, teacher_id=teacher_id).first()
    if exists:
        flash('Solicitação de mentoria já enviada ou ativa.', 'info')
    else:
        new_mentorship = Mentorship(student_id=current_user.id, teacher_id=teacher_id, status='active') # Auto-active for simplicity here
        db.session.add(new_mentorship)
        db.session.commit()
        flash('Mentor vinculado com sucesso!', 'success')
    return redirect(url_for('student_dashboard'))

# --- Public Route ---

@app.route('/verify/<string:code>')
def verify_certificate(code):
    cert = Certificate.query.filter_by(verification_code=code).first()
    return render_template('public/verify.html', cert=cert)

@app.route('/waiting')
@login_required
def waiting():
    if current_user.is_approved:
        return redirect(url_for('dashboard'))
    return render_template('auth/waiting.html')

@app.route('/study/validate/<int:session_id>', methods=['POST'])
@role_required('student')
def validate_focus(session_id):
    session = StudySession.query.get_or_404(session_id)
    if session.student_id != current_user.id:
        return redirect(url_for('dashboard'))
    
    session.is_validated = True
    db.session.commit()
    return {"status": "success"}

# Placeholder for auth (will be expanded)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        # Admin credentials enforcement
        if email == 'johnny.oliveira@sp.senai.br' and password == 'Jb@46431194':
            admin = User.query.filter_by(email=email).first()
            if not admin:
                admin = User(name='Johnny Oliveira', email=email, role='admin', is_approved=True)
                admin.set_password(password)
                db.session.add(admin)
                db.session.commit()
            login_user(admin)
            return redirect(url_for('admin_dashboard'))

        if user and user.check_password(password):
            login_user(user, force=True)
            if user.needs_password_change:
                flash('Sua senha foi resetada. Por favor, crie uma nova senha de segurança.', 'warning')
                return redirect(url_for('change_password'))
            if not user.is_approved:
                return redirect(url_for('waiting'))
            return redirect(url_for('dashboard'))
        flash('Email ou senha inválidos.', 'danger')
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student') # Default to student
        objective = request.form.get('objective')
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'danger')
            return redirect(url_for('register'))
            
        new_user = User(name=name, email=email, role=role, study_objective=objective)
        new_user.set_password(password)
        
        # Auto-activate first user as admin if needed, otherwise wait for approval
        if User.query.count() == 0:
            new_user.role = 'admin'
            new_user.is_approved = True
        
        db.session.add(new_user)
        db.session.commit()
        flash('Cadastro realizado com sucesso! Aguarde a aprovação do administrador.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html')

from sqlalchemy import text, inspect

def ensure_db_schema():
    with app.app_context():
        # First ensure tables exist
        db.create_all()
        
        # Then check columns in 'users' table
        inspector = inspect(db.engine)
        if 'users' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('users')]
            
            with db.engine.connect() as conn:
                # 1. Handle is_approved (rename or add)
                if 'is_approved' not in columns:
                    if 'is_active' in columns:
                        try:
                            conn.execute(text("ALTER TABLE users RENAME COLUMN is_active TO is_approved;"))
                            print("Coluna is_active renomeada para is_approved.")
                        except Exception as e:
                            print(f"Erro ao renomear: {e}")
                    else:
                        try:
                            # Use BOOLEAN DEFAULT FALSE which works for both SQLite and Postgres
                            conn.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT FALSE;"))
                            print("Coluna is_approved adicionada.")
                        except Exception as e:
                            print(f"Erro ao adicionar is_approved: {e}")
                    conn.commit()

                # 2. Handle needs_password_change
                # Re-inspect columns after potential rename
                columns = [c['name'] for c in inspector.get_columns('users')]
                if 'needs_password_change' not in columns:
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN needs_password_change BOOLEAN DEFAULT FALSE;"))
                        print("Coluna needs_password_change adicionada.")
                    except Exception as e:
                        print(f"Erro ao adicionar needs_password_change: {e}")
                    conn.commit()

ensure_db_schema()

@app.route('/auth/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('auth/change_password.html')
            
        current_user.set_password(new_password)
        current_user.needs_password_change = False
        db.session.commit()
        flash('Senha atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('auth/change_password.html')

if __name__ == '__main__':
    app.run(debug=True)
