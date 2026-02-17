# Target SaaS - Plataforma de Gestão de Horas de Estudo

## 🚀 Sobre o Projeto
O **Target** é uma plataforma SaaS completa desenvolvida em Python/Flask, projetada para ajudar estudantes a gerenciarem, comprovarem e validarem suas horas de estudo para objetivos específicos como OAB, Concursos Públicos e Certificações. O sistema conta com a supervisão de Professores/Mentores e uma administração centralizada.

## 🛠️ Stack Tecnológica
- **Backend:** Python 3 + Flask
- **Banco de Dados:** SQLAlchemy (SQLite em dev, PostgreSQL em produção)
- **Frontend:** HTML5 + Jinja2 + TailwindCSS (CDN)
- **Autenticação:** Flask-Login + Werkzeug
- **Documentos:** ReportLab (Geração de Certificados PDF)
- **Hospedagem:** Preparado para Railway

## 👥 Perfis de Usuário

### 1. Administrador (Super Admin)
- Visão geral de métricas da plataforma (total de horas, usuários).
- Aprovação de novos cadastros de alunos e professores.
- Gestão de licenças e reset de senhas.

### 2. Professor / Mentor
- Gestão de alunos vinculados.
- Criação de **Planos de Estudo** com metas de horas por matéria.
- Visualização do progresso dos mentorados.

### 3. Aluno (Student)
- **Registro de Estudo:** Cronômetro (Start/Stop) para metas agendadas ou registro manual.
- **Materiais:** Envio de arquivos de comprovação e links de referência.
- **Certificados:** Geração de certificados digitais UUID com validade pública.
- **Validação de Foco:** Sistema de validação durante as sessões de estudo.

## 📋 Como Rodar Localmente

1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/devjohnnydev/Target.git
   cd Target
   ```

2. **Criar ambiente virtual e instalar dependências:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # No Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Iniciar a aplicação:**
   ```bash
   python main.py
   ```
   *Acesse em: `http://127.0.0.1:5000`*

## 🚆 Hospedagem no Railway

Este projeto está pronto para ser hospedado no **Railway**. Ele detecta automaticamente a variável de ambiente `DATABASE_URL` para conectar ao PostgreSQL.

1. Conecte seu repositório GitHub ao Railway.
2. Adicione um serviço de **PostgreSQL**.
3. O Railway configurará o `Procfile` automaticamente para rodar com **Gunicorn**.

## 🛡️ Validação de Certificados
Cada certificado gerado possui um código UUID único. A autenticidade pode ser verificada publicamente em:
`https://seu-dominio.com/verify/<uuid>`

---
Desenvolvido com ❤️ como um projeto de alta produtividade para estudantes.
