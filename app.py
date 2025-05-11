from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from supabase import create_client, Client
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"  # Substitua por uma chave segura

# Configuração do cliente Supabase usando URL e chave API
SUPABASE_URL = "https://dqtmjcwgzceqfolkbwfk.supabase.co"  # Substitua pela URL do seu projeto
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRxdG1qY3dnemNlcWZvbGtid2ZrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY5ODE3MzQsImV4cCI6MjA2MjU1NzczNH0.DTU9dtF39w7igQV2EENZNqKfBNtt50-u6C_hVC9ppt8"  # Substitua pela sua chave API (anon)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Rota para a página de login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cpf = request.form.get("cpf")
        password = request.form.get("password")
        print(f"Tentativa de login com CPF: {cpf}, Senha: {password}")  # Depuração

        try:
            # Buscar o usuário no banco de dados
            print(f"Consultando Supabase com CPF: {cpf}")  # Log adicional
            response = supabase.table("usuarios").select("*").eq("cpf", cpf).execute()
            print(f"Resposta do Supabase: {response.data}")  # Log adicional
            user = response.data[0] if response.data else None

            if user:
                stored_password = user["senha"]
                user_name = user["nome"]
                user_cargo = user["cargo"]
                print(f"Usuário encontrado: {user_name}, Cargo: {user_cargo}")  # Log adicional
                if password == stored_password:  # Em produção, use bcrypt.compare
                    session["user"] = {
                        "cpf": cpf,
                        "name": user_name,
                        "cargo": user_cargo
                    }
                    print("Login bem-sucedido, redirecionando para /scan")  # Depuração
                    return redirect(url_for("scan"))
                else:
                    print("Senha incorreta")  # Depuração
                    rendered = render_template("login.html", error="Credenciais inválidas. Tente novamente.")
                    print("Renderizando login.html (POST):", rendered[:500])  # Depuração
                    return rendered
            else:
                print("Usuário não encontrado")  # Depuração
                rendered = render_template("login.html", error="Credenciais inválidas. Tente novamente.")
                print("Renderizando login.html (POST):", rendered[:500])  # Depuração
                return rendered
        except Exception as e:
            print(f"Erro ao buscar usuário no banco: {str(e)}")
            return render_template("login.html", error="Erro ao fazer login. Tente novamente."), 500

    print("Renderizando login.html (GET)")  # Depuração
    rendered = render_template("login.html", error=None)
    print("Conteúdo renderizado (GET):", rendered[:500])  # Depuração
    return rendered

# Rota para a página de leitura de QR code
@app.route("/scan", methods=["GET"])
def scan():
    if "user" not in session:
        print("Usuário não autenticado, redirecionando para login")  # Depuração
        return redirect(url_for("login"))

    user = session["user"]
    try:
        # Buscar turmas associadas ao polo/unidade do professor
        query = supabase.table("turmas").select("""
            id, nome, 
            disciplinas (nome as disciplina, tipo), 
            polos (nome as polo), 
            unidades (nome as unidade)
        """)

        if user["cargo"] in ["diretor", "monitor"]:
            response = supabase.table("usuarios").select("unidade_id").eq("cpf", user["cpf"]).execute()
            unidade_id = response.data[0]["unidade_id"] if response.data else None
            if unidade_id:
                query = query.eq("unidade_id", unidade_id)
        elif user["cargo"] == "coordenador":
            response = supabase.table("usuarios").select("polo_id").eq("cpf", user["cpf"]).execute()
            polo_id = response.data[0]["polo_id"] if response.data else None
            if polo_id:
                query = query.eq("polo_id", polo_id)

        response = query.execute()
        turmas = []
        for turma in response.data:
            turmas.append({
                "id": turma["id"],
                "nome": turma["nome"],
                "disciplina": turma["disciplinas"]["disciplina"],
                "tipo": turma["disciplinas"]["tipo"],
                "polo": turma["polos"]["polo"],
                "unidade": turma["unidades"]["unidade"]
            })
    except Exception as e:
        print(f"Erro ao buscar turmas: {str(e)}")
        turmas = []

    print("Renderizando scan.html")  # Depuração
    return render_template("scan.html", turmas=turmas)

# Rota para registrar presença
@app.route("/register_attendance", methods=["POST"])
def register_attendance():
    if "user" not in session:
        print("Usuário não autenticado para registrar presença")  # Depuração
        return jsonify({"error": "Não autenticado"}), 401

    data = request.json
    qr_data = data.get("qr_data")
    turma_id = data.get("turma_id")
    print(f"Recebido QR code: {qr_data}, Turma ID: {turma_id}")  # Depuração

    try:
        student_data = json.loads(qr_data)
        student_id = student_data.get("id")
        student_name = student_data.get("name")

        if not student_id or not student_name or not turma_id:
            print("Dados incompletos no QR code ou turma não selecionada")  # Depuração
            return jsonify({"error": "Dados incompletos no QR code ou turma não selecionada"}), 400

        # Verificar se o aluno existe e está matriculado na turma
        response = supabase.table("alunos").select("*, matriculas!inner(id as matricula_id)").eq("id", student_id).eq("matriculas.turma_id", turma_id).execute()
        student = response.data[0] if response.data else None

        if not student:
            print("Aluno não encontrado")  # Depuração
            return jsonify({"error": "Aluno não encontrado"}), 404

        matricula_id = student.get("matriculas", [{}])[0].get("matricula_id")
        if not matricula_id:
            print("Aluno não está matriculado nesta turma")  # Depuração
            return jsonify({"error": "Aluno não está matriculado nesta turma"}), 403

        # Verificar se já há uma presença registrada para esta aula (mesmo dia)
        today = datetime.now().strftime("%Y-%m-%d")
        response = supabase.table("presencas").select("*").eq("aluno_id", student_id).eq("turma_id", turma_id).gte("data_hora", f"{today}T00:00:00").lte("data_hora", f"{today}T23:59:59").execute()
        existing_presence = response.data[0] if response.data else None

        if existing_presence:
            print("Presença já registrada para esta aula hoje")  # Depuração
            return jsonify({"error": "Presença já registrada para esta aula hoje"}), 400

        # Registrar a presença
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        response = supabase.table("presencas").insert({
            "aluno_id": student_id,
            "turma_id": turma_id,
            "data_hora": timestamp
        }).execute()

        print(f"Presença registrada: {student_name} (ID: {student_id}) às {timestamp}")  # Depuração
        return jsonify({"message": f"Presença registrada: {student_name} (ID: {student_id}) às {timestamp}"})
    except Exception as e:
        print(f"Erro ao registrar presença: {str(e)}")
        return jsonify({"error": f"Erro ao registrar presença: {str(e)}"}), 500

# Rota para visualizar presenças
@app.route("/attendances", methods=["GET"])
def view_attendances():
    if "user" not in session:
        print("Usuário não autenticado, redirecionando para login")  # Depuração
        return redirect(url_for("login"))

    user = session["user"]
    try:
        # Buscar presenças com joins
        query = supabase.table("presencas").select("""
            *, 
            alunos (nome as student_name, matricula), 
            turmas (nome as turma_nome, disciplinas (nome as disciplina, tipo as disciplina_tipo), polos (id as polo_id), unidades (id as unidade_id))
        """)

        if user["cargo"] in ["diretor", "monitor"]:
            response = supabase.table("usuarios").select("unidade_id").eq("cpf", user["cpf"]).execute()
            unidade_id = response.data[0]["unidade_id"] if response.data else None
            if unidade_id:
                query = query.eq("turmas.unidade_id", unidade_id)
        elif user["cargo"] == "coordenador":
            response = supabase.table("usuarios").select("polo_id").eq("cpf", user["cpf"]).execute()
            polo_id = response.data[0]["polo_id"] if response.data else None
            if polo_id:
                query = query.eq("turmas.polo_id", polo_id)

        response = query.order("data_hora", desc=True).execute()
        attendances = []
        for row in response.data:
            attendances.append({
                "student_id": row["aluno_id"],
                "student_name": row["alunos"]["student_name"],
                "matricula": row["alunos"]["matricula"],
                "turma_nome": row["turmas"]["turma_nome"],
                "disciplina": row["turmas"]["disciplinas"]["disciplina"],
                "disciplina_tipo": row["turmas"]["disciplinas"]["disciplina_tipo"],
                "timestamp": datetime.fromisoformat(row["data_hora"]).strftime("%Y-%m-%d %H:%M:%S"),
                "date": datetime.fromisoformat(row["data_hora"]).strftime("%Y-%m-%d")
            })
    except Exception as e:
        print(f"Erro ao buscar presenças: {str(e)}")
        attendances = []

    print("Renderizando attendances.html")  # Depuração
    return render_template("attendances.html", attendances=attendances)

# Rota para logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    print("Usuário fez logout, redirecionando para login")  # Depuração
    return redirect(url_for("login"))

# Rota para o manifest.json
@app.route("/manifest.json")
def serve_manifest():
    return send_from_directory("static", "manifest.json")

# Rota para o service-worker.js
@app.route("/service-worker.js")
def serve_service_worker():
    return send_from_directory("static", "service-worker.js")

if __name__ == "__main__":
    app.run(debug=True, port=5000)