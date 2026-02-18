import os
import uuid
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, License, StudySession, StudyPlan, Mentorship, Certificate, Submission, AssignedTask
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

# Kuryos AI Config (Groq)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "SUA_CHAVE_AQUI")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

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
    # Filters from request
    subject_filter = request.args.get('subject')
    date_filter = request.args.get('date') # YYYY-MM-DD
    sort_order = request.args.get('sort', 'desc') # 'asc' or 'desc'

    # Base query for stats
    sessions_query = StudySession.query

    if subject_filter:
        sessions_query = sessions_query.filter(StudySession.subject.ilike(f"%{subject_filter}%"))
    if date_filter:
        if date_filter == 'today':
            target_date = datetime.utcnow().date()
            sessions_query = sessions_query.filter(StudySession.date == target_date)
            date_filter = target_date.strftime('%Y-%m-%d')
        else:
            try:
                target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                sessions_query = sessions_query.filter(StudySession.date == target_date)
            except:
                pass

    # Aggregated Stats
    total_minutes = db.session.query(db.func.sum(StudySession.duration_minutes)).filter(
        StudySession.id.in_(sessions_query.with_entities(StudySession.id))
    ).scalar() or 0
    total_hours = round(total_minutes / 60, 1)

    # Student Ranking Data
    # Calculate sum of minutes per student
    student_stats = db.session.query(
        User.id,
        User.name,
        User.email,
        User.is_approved,
        User.photo_url,
        User.profile_image_type,
        db.func.sum(StudySession.duration_minutes).label('total_minutes')
    ).join(StudySession, User.id == StudySession.student_id, isouter=True)\
     .filter(User.role == 'student')\
     .group_by(User.id, User.photo_url, User.profile_image_type)

    # Apply sorting
    if sort_order == 'asc':
        student_stats = student_stats.order_by(db.text('total_minutes ASC'))
    else:
        student_stats = student_stats.order_by(db.text('total_minutes DESC'))

    all_students = student_stats.all()
    
    # Format ranking results
    ranking = []
    for s_id, s_name, s_email, s_approved, s_photo, s_img_type, s_minutes in all_students:
        ranking.append({
            'id': s_id,
            'name': s_name,
            'email': s_email,
            'is_approved': s_approved,
            'photo_url': s_photo,
            'profile_image_type': s_img_type,
            'hours': round((s_minutes or 0) / 60, 1)
        })

    # Active sessions for Real-time Monitoring
    active_sessions = StudySession.query.filter(StudySession.end_time == None).all()

    # Pending Users for Approval
    pending_users = User.query.filter_by(is_approved=False).order_by(User.created_at.desc()).all()

    licenses = License.query.all()
    # Unique subjects for the filter dropdown
    available_subjects = db.session.query(StudySession.subject).distinct().all()
    available_subjects = [s[0] for s in available_subjects]

    return render_template('admin/dashboard.html', 
                         ranking=ranking, 
                         total_hours=total_hours, 
                         licenses=licenses,
                         active_sessions=active_sessions,
                         pending_users=pending_users,
                         available_subjects=available_subjects,
                         current_subject=subject_filter,
                         current_date=date_filter,
                         current_sort=sort_order)

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_approve(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'Usuário {user.name} aprovado com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:user_id>', methods=['POST'])
@role_required('admin')
def admin_reject(user_id):
    user = User.query.get_or_404(user_id)
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f'Solicitação de {name} removida.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/analytics')
@role_required('admin')
def admin_analytics():
    # 1. Study time per Student
    time_per_student = db.session.query(
        User.name,
        db.func.sum(StudySession.duration_minutes).label('total_minutes')
    ).join(StudySession, User.id == StudySession.student_id)\
     .group_by(User.id, User.name)\
     .order_by(db.text('total_minutes DESC')).all()
    
    # 2. Study time per Subject/Title
    time_per_subject = db.session.query(
        StudySession.subject,
        db.func.sum(StudySession.duration_minutes).label('total_minutes')
    ).group_by(StudySession.subject)\
     .order_by(db.text('total_minutes DESC')).all()
    
    # 3. Study time per Date (Last 30 days)
    last_30_days = datetime.utcnow().date() - timedelta(days=30)
    time_per_day = db.session.query(
        StudySession.date,
        db.func.sum(StudySession.duration_minutes).label('total_minutes')
    ).filter(StudySession.date >= last_30_days)\
     .group_by(StudySession.date)\
     .order_by(StudySession.date.asc()).all()

    # Format data for template (converting to hours)
    metrics = {
        'students': [{'name': r[0], 'hours': round(r[1]/60, 1)} for r in time_per_student],
        'subjects': [{'name': r[0], 'hours': round(r[1]/60, 1)} for r in time_per_subject],
        'dates': [{'date': r[0].strftime('%d/%m'), 'hours': round(r[1]/60, 1)} for r in time_per_day]
    }

    return render_template('admin/analytics.html', metrics=metrics)


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
    # Fetch tasks created by this teacher
    tasks = AssignedTask.query.filter_by(teacher_id=current_user.id).order_by(AssignedTask.created_at.desc()).all()
    return render_template('teacher/dashboard.html', students=students, tasks=tasks)

@app.route('/teacher/task/create', methods=['POST'])
@role_required('teacher')
def create_task():
    title = request.form.get('title')
    description = request.form.get('description')
    external_link = request.form.get('external_link')
    student_id = request.form.get('student_id') # Can be None for general tasks
    
    file = request.files.get('file')
    attachment_path = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"task_{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        attachment_path = unique_filename
        
    new_task = AssignedTask(
        teacher_id=current_user.id,
        student_id=student_id if student_id else None,
        title=title,
        description=description,
        external_link=external_link,
        attachment_path=attachment_path
    )
    db.session.add(new_task)
    db.session.commit()
    flash('Nova tarefa assistida designada!', 'success')
    return redirect(url_for('teacher_dashboard'))

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

@app.route('/student/profile', methods=['GET', 'POST'])
@role_required('student')
def student_profile():
    if request.method == 'POST':
        user = User.query.get(current_user.id)
        user.study_objective = request.form.get('study_objective')
        user.search_intent = request.form.get('search_intent')
        
        img_type = request.form.get('image_type') # 'local' or 'url'
        user.profile_image_type = img_type
        
        if img_type == 'url':
            user.photo_url = request.form.get('photo_url')
        else:
            file = request.files.get('local_photo')
            if file and allowed_file(file.filename):
                filename = f"profile_{user.id}_{uuid.uuid4().hex[:8]}_{file.filename}"
                os.makedirs('static/uploads/profiles', exist_ok=True)
                file.save(os.path.join('static/uploads/profiles', filename))
                user.photo_url = filename
        
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('student_profile'))
        
    return render_template('student/profile.html', user=current_user)

@app.route('/student')
@role_required('student')
def student_dashboard():
    sessions = StudySession.query.filter_by(student_id=current_user.id).order_by(StudySession.start_time.desc()).all()
    plans = StudyPlan.query.filter_by(student_id=current_user.id).all()
    total_minutes = sum(s.duration_minutes for s in sessions if s.duration_minutes)
    total_hours = round(total_minutes / 60, 1)
    all_teachers = User.query.filter_by(role='teacher', is_approved=True).all()
    
    # Fetch tasks: specific to student OR for everyone
    assigned_tasks = AssignedTask.query.filter(
        (AssignedTask.student_id == current_user.id) | (AssignedTask.student_id == None)
    ).order_by(AssignedTask.created_at.desc()).all()
    
    # Fetch certificates (Internal and External)
    certificates = Certificate.query.filter_by(student_id=current_user.id).order_by(Certificate.issue_date.desc()).all()
    
    return render_template('student/dashboard.html', 
                         sessions=sessions, 
                         plans=plans, 
                         total_hours=total_hours, 
                         all_teachers=all_teachers,
                         assigned_tasks=assigned_tasks,
                         certificates=certificates)

@app.route('/study/log', methods=['POST'])
@role_required('student')
def log_study():
    subject = request.form.get('subject')
    subtitle = request.form.get('subtitle', '')
    minutes = int(request.form.get('minutes'))
    
    new_session = StudySession(
        student_id=current_user.id,
        subject=subject,
        subtitle=subtitle,
        start_time=datetime.utcnow() - timedelta(minutes=minutes),
        end_time=datetime.utcnow(),
        duration_minutes=minutes,
        type='free',
        is_validated=True
    )
    db.session.add(new_session)
    
    # Update Study Plan progress
    plan = StudyPlan.query.filter_by(student_id=current_user.id, target_subject=subject).first()
    if plan:
        plan.completed_hours += round(minutes / 60, 2)
        
    db.session.commit()
    flash('Hora de estudo registrada!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/study/start', methods=['POST'])
@role_required('student')
def start_session():
    subject = request.form.get('subject')
    subtitle = request.form.get('subtitle', '')
    task_id = request.form.get('task_id')
    
    # Check if there's already an active session
    active = StudySession.query.filter_by(student_id=current_user.id, end_time=None).first()
    if active:
        flash('Você já tem uma sessão ativa!', 'warning')
        return redirect(url_for('student_dashboard'))
        
    new_session = StudySession(
        student_id=current_user.id,
        subject=subject,
        subtitle=subtitle,
        task_id=task_id if task_id else None,
        start_time=datetime.utcnow(),
        type='assisted' if task_id else 'scheduled'
    )
    db.session.add(new_session)
    db.session.commit()
    flash(f'Foco iniciado em {subject}!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/study/stop/<int:session_id>', methods=['POST'])
@role_required('student')
def stop_session(session_id):
    session = StudySession.query.get_or_404(session_id)
    if session.student_id != current_user.id:
        return redirect(url_for('dashboard'))
        
    session.end_time = datetime.utcnow()
    duration = (session.end_time - session.start_time).total_seconds() / 60
    session.duration_minutes = int(duration)
    session.is_validated = True
    
    # Submission details
    session.completion_comment = request.form.get('comment')
    session.completion_link = request.form.get('link')
    
    file = request.files.get('file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"delivery_{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        session.completion_file = unique_filename
    
    # Update Study Plan progress
    plan = StudyPlan.query.filter_by(student_id=current_user.id, target_subject=session.subject).first()
    if plan:
        plan.completed_hours += round(duration / 60, 2)
        
    db.session.commit()
    flash('Missão cumprida! Registro salvo.', 'success')
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

@app.route('/certificate/upload-external', methods=['POST'])
@role_required('student')
def upload_external_certificate():
    description = request.form.get('description')
    hours = float(request.form.get('hours', 0))
    file = request.files.get('file')
    
    if not file or not allowed_file(file.filename):
        flash('Arquivo inválido ou não selecionado.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    filename = secure_filename(file.filename)
    unique_filename = f"ext_cert_{int(datetime.utcnow().timestamp())}_{filename}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
    
    new_cert = Certificate(
        student_id=current_user.id,
        verification_code=f"EXT-{uuid.uuid4().hex[:8].upper()}",
        total_hours=hours,
        pdf_path=unique_filename,
        is_external=True,
        external_issuer=request.form.get('issuer', 'Externo')
    )
    db.session.add(new_cert)
    db.session.commit()
    flash('Certificado externo registrado com sucesso!', 'success')
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
    
    if not teacher_id or not str(teacher_id).isdigit():
        flash('Por favor, selecione um mentor válido.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    teacher = User.query.filter_by(id=teacher_id, role='teacher').first()
    if not teacher:
        flash('Mentor não encontrado ou inválido.', 'danger')
        return redirect(url_for('student_dashboard'))

    # Check if already exists
    exists = Mentorship.query.filter_by(student_id=current_user.id, teacher_id=teacher_id).first()
    if exists:
        flash('Você já possui uma solicitação ou vínculo com este mentor.', 'info')
    else:
        try:
            new_mentorship = Mentorship(student_id=current_user.id, teacher_id=teacher_id, status='active')
            db.session.add(new_mentorship)
            db.session.commit()
            flash(f'Vínculo com {teacher.name} estabelecido com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao vincular mentor: {e}")
            flash('Erro técnico ao processar o vínculo. Tente novamente.', 'danger')
            
    return redirect(url_for('student_dashboard'))

@app.route('/study/plan/update-status/<int:plan_id>', methods=['POST'])
@role_required('student')
def update_plan_status(plan_id):
    plan = StudyPlan.query.get_or_404(plan_id)
    if plan.student_id != current_user.id:
        return {"error": "Unauthorized"}, 403
        
    new_status = request.json.get('status')
    if new_status in ['backlog', 'active', 'completed']:
        plan.status = new_status
        db.session.commit()
        return {"status": "success", "new_status": new_status}
    return {"error": "Invalid status"}, 400

@app.route('/ai/ask', methods=['POST'])
@role_required('student')
def ai_ask():
    user_question = request.json.get('question')
    if not user_question:
        return {"error": "No question provided"}, 400

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # System prompt to define Kuryos AI personality
    system_prompt = (
        "Você é o Kuryos AI, um Mentor de Estudos Premium e conciso. "
        "Seu objetivo é ajudar alunos do SENAI e usuários da plataforma Target SaaS a tirar dúvidas técnicas e de estudo. "
        "Seja motivador, use tom futurista e mantenha as respostas diretas ao ponto. "
        "Formate suas respostas em Markdown (negrito, listas, etc) para facilitar a leitura."
    )

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ],
        "temperature": 0.7,
        "max_tokens": 1024
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        result = response.json()
        ai_message = result['choices'][0]['message']['content']
        return {"answer": ai_message}
    except Exception as e:
        print(f"Groq API Error: {e}")
        return {"error": "O Kuryos AI está temporariamente offline. Tente novamente em instantes."}, 500

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
    print(">>> [DB SYNC] Iniciando sincronização do banco de dados Phase 2...")
    with app.app_context():
        try:
            db.create_all()
            print(">>> [DB SYNC] Tabelas base conferidas.")
        except Exception as e:
            print(f">>> [DB SYNC] Erro fatal no create_all: {e}")
        
        try:
            inspector = inspect(db.engine)
            
            # Check users table
            columns_users = [c['name'] for c in inspector.get_columns('users')]
            with db.engine.connect() as conn:
                if 'is_approved' not in columns_users:
                    if 'is_active' in columns_users:
                        conn.execute(text("ALTER TABLE users RENAME COLUMN is_active TO is_approved;"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT FALSE;"))
                if 'needs_password_change' not in columns_users:
                    conn.execute(text("ALTER TABLE users ADD COLUMN needs_password_change BOOLEAN DEFAULT FALSE;"))
                if 'profile_image_type' not in columns_users:
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_image_type VARCHAR(20) DEFAULT 'url';"))
                if 'search_intent' not in columns_users:
                    conn.execute(text("ALTER TABLE users ADD COLUMN search_intent TEXT;"))
                
                # Check study_sessions table
                columns_sessions = [c['name'] for c in inspector.get_columns('study_sessions')]
                if 'task_id' not in columns_sessions:
                    conn.execute(text("ALTER TABLE study_sessions ADD COLUMN task_id INTEGER;"))
                if 'subtitle' not in columns_sessions:
                    conn.execute(text("ALTER TABLE study_sessions ADD COLUMN subtitle VARCHAR(100);"))
                if 'completion_comment' not in columns_sessions:
                    conn.execute(text("ALTER TABLE study_sessions ADD COLUMN completion_comment TEXT;"))
                if 'completion_file' not in columns_sessions:
                    conn.execute(text("ALTER TABLE study_sessions ADD COLUMN completion_file VARCHAR(255);"))
                if 'completion_link' not in columns_sessions:
                    conn.execute(text("ALTER TABLE study_sessions ADD COLUMN completion_link VARCHAR(255);"))
                
                # Check certificates table
                columns_certs = [c['name'] for c in inspector.get_columns('certificates')]
                if 'is_external' not in columns_certs:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN is_external BOOLEAN DEFAULT FALSE;"))
                if 'external_issuer' not in columns_certs:
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN external_issuer VARCHAR(100);"))
                
                # Check study_plans table
                columns_plans = [c['name'] for c in inspector.get_columns('study_plans')]
                if 'status' not in columns_plans:
                    conn.execute(text("ALTER TABLE study_plans ADD COLUMN status VARCHAR(20) DEFAULT 'active';"))

                conn.commit()
                print(">>> [DB SYNC] Schema Phase 2 sincronizado.")
        except Exception as e:
            print(f">>> [DB SYNC] Erro durante sincronização: {e}")
            db.session.rollback()

ensure_db_schema()

@app.route('/health')
def health_check():
    try:
        User.query.first()
        return {"status": "healthy", "database": "connected", "schema": "up_to_date"}, 200
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

@app.route('/auth/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or new_password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('auth/change_password.html')
            
        current_user.set_password(new_password)
        current_user.needs_password_change = False
        db.session.commit()
        flash('Sua chave de acesso foi atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('auth/change_password.html')

if __name__ == '__main__':
    app.run(debug=True)
