import os
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from flask import url_for

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
    c.drawCentredString(width/2, height - 3*cm, "TARGET SaaS")
    
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
