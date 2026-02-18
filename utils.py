import os
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from flask import url_for
from datetime import datetime

def generate_study_certificate(student_name, total_hours, verification_code, objective):
    """Generates a PDF certificate for study hours."""
    filename = f"certificate_{verification_code}.pdf"
    # Ensure static/certificates directory exists
    os.makedirs('static/certificates', exist_ok=True)
    filepath = os.path.join('static/certificates', filename)
    
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    # Border
    c.setStrokeColorRGB(0.1, 0.1, 0.4)
    c.setLineWidth(5)
    c.rect(1*cm, 1*cm, width-2*cm, height-2*cm)
    
    # Title
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height - 5*cm, "CERTIFICADO DE ESTUDOS")
    
    # Logo text
    c.setFont("Helvetica-Bold", 40)
    c.setFillColorRGB(0.2, 0.2, 0.6)
    c.drawString(100, 750, "TARGET - CERTIFICADO DE ESTUDOS")
    
    # Content
    c.setFont("Helvetica", 18)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(width/2, height - 9*cm, "Certificamos que o(a) estudante")
    
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 10.5*cm, student_name.upper())
    
    c.setFont("Helvetica", 16)
    text = f"concluiu com êxito o total de {total_hours} horas de estudo"
    c.drawCentredString(width/2, height - 12*cm, text)
    c.drawCentredString(width/2, height - 13*cm, f"com foco em: {objective}")
    
    # Footer / Verification
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width/2, 4*cm, f"Código de Verificação: {verification_code}")
    c.drawCentredString(width/2, 3.5*cm, f"Valide em: http://target.saas/verify/{verification_code}")
    
    c.showPage()
    c.save()
    
    return filepath


def generate_subject_study_report(student_name, subject, sessions, total_hours):
    """Generates a detailed PDF report for a specific subject's study sessions."""
    filename = f"report_{subject.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.pdf"
    os.makedirs('static/reports', exist_ok=True)
    filepath = os.path.join('static/reports', filename)
    
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    # Header
    c.setFillColorRGB(0.1, 0.7, 0.5)  # Emerald color
    c.rect(0, height - 3*cm, width, 3*cm, fill=True, stroke=False)
    
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(2*cm, height - 2*cm, "RELATÓRIO DE ESTUDOS")
    
    c.setFont("Helvetica", 12)
    c.drawString(2*cm, height - 2.5*cm, f"Aluno: {student_name}")
    c.drawString(2*cm, height - 2.8*cm, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Subject Title
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(2*cm, height - 4.5*cm, f"Assunto: {subject}")
    
    # Summary Box
    c.setFillColorRGB(0.95, 0.95, 0.95)
    c.rect(2*cm, height - 7*cm, width - 4*cm, 2*cm, fill=True, stroke=True)
    
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2.5*cm, height - 5.5*cm, f"Total de Horas: {total_hours}H")
    c.drawString(2.5*cm, height - 6*cm, f"Número de Sessões: {len(sessions)}")
    
    # Sessions Table Header
    y_position = height - 8.5*cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2*cm, y_position, "Data")
    c.drawString(5*cm, y_position, "Duração")
    c.drawString(8*cm, y_position, "Comentário")
    
    # Draw line under header
    c.line(2*cm, y_position - 0.2*cm, width - 2*cm, y_position - 0.2*cm)
    
    # Sessions List
    y_position -= 0.8*cm
    c.setFont("Helvetica", 9)
    
    for session in sessions:
        if y_position < 3*cm:  # New page if needed
            c.showPage()
            y_position = height - 2*cm
            c.setFont("Helvetica", 9)
        
        date_str = session.start_time.strftime('%d/%m/%Y')
        duration_str = f"{session.duration_minutes}min"
        comment_str = (session.completion_comment or "Sem comentário")[:40] + "..." if session.completion_comment and len(session.completion_comment) > 40 else (session.completion_comment or "Sem comentário")
        
        c.drawString(2*cm, y_position, date_str)
        c.drawString(5*cm, y_position, duration_str)
        c.drawString(8*cm, y_position, comment_str)
        
        y_position -= 0.6*cm
    
    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(width/2, 1.5*cm, "TARGET - Sistema de Gestão de Estudos")
    c.drawCentredString(width/2, 1*cm, "Este relatório foi gerado automaticamente")
    
    c.showPage()
    c.save()
    
    return filename
