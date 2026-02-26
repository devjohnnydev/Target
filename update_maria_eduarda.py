import os
from datetime import datetime, timedelta
from main import app, db
from models import User, StudySession
from utils import get_now

def update_maria_eduarda():
    with app.app_context():
        # 1. Target Data
        target_name = "Maria Eduarda"
        target_minutes = (2650 * 60) + 34  # Total 159,034 minutes
        pivot_subject = "Monitoramento do Sistema"
        
        # 2. Find Student (Auto-create if missing)
        student = User.query.filter(User.name.ilike(f"%{target_name}%")).first()
        if not student:
            print(f"Estudante '{target_name}' não encontrada. Criando novo registro...")
            student = User(
                name="Maria Eduarda Alves Lourenço",
                email="maria.eduarda@estudante.com",
                role="student",
                is_approved=True
            )
            student.set_password("muda123") # Default password
            db.session.add(student)
            db.session.flush() # Get ID
            print(f"Estudante criada com ID: {student.id}")
        else:
            print(f"Estudante encontrada: {student.name} (ID: {student.id})")
        
        # 3. Find Pivot Session (Monitoramento do Sistema)
        pivot_session = StudySession.query.filter_by(
            student_id=student.id, 
            subject=pivot_subject
        ).order_by(StudySession.start_time).first()
        
        if not pivot_session:
            # If pivot doesn't exist, we use current time as reference
            print(f"Aviso: Atividade '{pivot_subject}' não encontrada. Usando data atual como referência.")
            reference_time = get_now()
        else:
            reference_time = pivot_session.start_time
            print(f"Atividade pivô encontrada em: {reference_time}")

        # 4. Calculate Current Total (We want to ENSURE she gets +2650:34 legacy hours)
        # The user wants her to have 2650:34 PLUS what she's doing now.
        # So we insert exactly 2650:34 as new historical records.
        
        minutes_to_add = target_minutes 
        print(f"Inserindo carga horária legada de {minutes_to_add} minutos ({minutes_to_add/60:.2f} horas)...")

        # 5. Insert Activities (balancing to reach target)
        # We will create large blocks of "Estudo Base" or "Pesquisa" to reach the quota rapidly
        # but following a plausible chronological order (going backwards from reference_time)
        
        current_ref = reference_time - timedelta(minutes=10) # Start 10 mins before pivot
        activity_count = 0
        
        # We'll insert in blocks of 8 hours (480 mins) to simulate full study days
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
            current_ref = start_time - timedelta(hours=16) # Gap to next previous day
            activity_count += 1
            
            if activity_count % 50 == 0:
                print(f"Processados {activity_count} blocos...")

        db.session.commit()
        print(f"Sucesso! {activity_count} atividades inseridas para alcançar 2.650:34 horas.")

if __name__ == "__main__":
    update_maria_eduarda()
