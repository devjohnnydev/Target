import os
from datetime import datetime, timedelta
from main import app, db
from models import User, StudySession
from utils import get_now

def fix_production():
    with app.app_context():
        # 1. Correct Users from Screenshot
        targets = [
            {"email": "lucgarcbeni@gmail.com", "name": "LUCAS GARCIA BENI"},
            {"email": "fuskenji@gmail.com", "name": "GUILHERME KENJI FUSUMA"}
        ]
        
        legacy_subtitle = "Carga Horária Legada"
        new_subject = "Horas Retroativas"
        
        for t in targets:
            user = User.query.filter((User.email == t['email']) | (User.name.ilike(f"%{t['name']}%"))).first()
            
            if user:
                print(f"\n--- Corrigindo {user.name} (ID: {user.id}) ---")
                
                # Deletar sessões que pareçam ser legado (Carga Horária Legada ou Fundamentos e Pesquisas com 480min)
                deleted = StudySession.query.filter(
                    StudySession.student_id == user.id,
                    ((StudySession.subtitle == legacy_subtitle) | (StudySession.subject == "Fundamentos e Pesquisas"))
                ).delete()
                print(f"Sessões legadas antigas removidas: {deleted}")
                
                # Inserir exatamente 700h (42000 minutos)
                minutes_to_add = 700 * 60
                activity_count = 0
                # Usar uma data de referência no passado para não chocar com o "hoje"
                current_ref = datetime(2026, 2, 25, 18, 0) 
                
                while minutes_to_add > 0:
                    block_mins = min(480, minutes_to_add)
                    start_time = current_ref - timedelta(minutes=block_mins)
                    
                    new_session = StudySession(
                        student_id=user.id,
                        subject=new_subject,
                        subtitle=legacy_subtitle,
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
                
                print(f"Total de {activity_count} novas sessões de 'Horas Retroativas' (700h) inseridas.")
            else:
                print(f"\nERRO: Usuário {t['name']} ({t['email']}) não encontrado!")

        # 2. Cleanup "Auto-created" duplicates from previous attempt
        duplicates = User.query.filter(User.name.contains("(Auto-created)")).all()
        for d in duplicates:
            print(f"Limpando usuário duplicado: {d.name} (ID: {d.id})")
            db.session.delete(d)
        
        db.session.commit()
        print("\nSincronização finalizada com sucesso.")

if __name__ == "__main__":
    fix_production()
