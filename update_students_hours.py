import os
from datetime import datetime, timedelta
from main import app, db
from models import User, StudySession
from utils import get_now

def update_student_hours(target_name, target_hours):
    target_minutes = target_hours * 60
    pivot_subject = "Monitoramento do Sistema"
    
    print(f"\n--- Processando {target_name} ---")
    
    with app.app_context():
        # 1. Find Student
        student = User.query.filter(User.name.ilike(f"%{target_name}%")).first()
        if not student:
            print(f"Estudante '{target_name}' não encontrado/a. Criando novo registro...")
            # Basic fallback if they don't exist yet, although they likely do
            student = User(
                name=f"{target_name} (Auto-created)",
                email=f"{target_name.lower().replace(' ', '.')}@estudante.com",
                role="student",
                is_approved=True
            )
            student.set_password("muda123")
            db.session.add(student)
            db.session.flush()
            print(f"Estudante criado/a com ID: {student.id}")
        else:
            print(f"Estudante encontrado/a: {student.name} (ID: {student.id})")
        
        # 2. Find Pivot Session
        pivot_session = StudySession.query.filter_by(
            student_id=student.id, 
            subject=pivot_subject
        ).order_by(StudySession.start_time).first()
        
        if not pivot_session:
            print(f"Aviso: Atividade '{pivot_subject}' não encontrada. Usando data atual como referência.")
            reference_time = get_now()
        else:
            reference_time = pivot_session.start_time
            print(f"Atividade pivô encontrada em: {reference_time}")

        # 3. Add Legacy Hours
        minutes_to_add = target_minutes 
        print(f"Inserindo carga horária legada de {minutes_to_add} minutos ({minutes_to_add/60:.2f} horas)...")

        current_ref = reference_time - timedelta(minutes=10)
        activity_count = 0
        
        while minutes_to_add > 0:
            block_mins = min(480, minutes_to_add)
            start_time = current_ref - timedelta(minutes=block_mins)
            
            new_session = StudySession(
                student_id=student.id,
                subject="Fundamentos e Pesquisas",
                subtitle="Carga Horária Legada",
                date=start_time.date(),
                start_time=start_time,
                end_time=current_ref,
                duration_minutes=block_mins,
                type='free',
                is_validated=True
            )
            db.session.add(new_session)
            
            minutes_to_add -= block_mins
            current_ref = start_time - timedelta(hours=16)
            activity_count += 1

        db.session.commit()
        print(f"Sucesso! {activity_count} atividades inseridas para {target_name}.")

if __name__ == "__main__":
    update_student_hours("Guilherme", 2000)
    update_student_hours("Lucas", 2000)
