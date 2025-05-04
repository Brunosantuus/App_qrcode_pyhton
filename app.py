from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
import json
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"  # Substitua por uma chave segura

# Usuários fictícios (em memória), usando CPF como chave
users = {
    "12345678900": {"password": "senha123", "name": "Professor João"}
}

# Caminho para o arquivo de presenças
ATTENDANCES_FILE = "data/attendances.json"

# Inicializar diretórios e arquivos
if not os.path.exists("data"):
    os.makedirs("data")
if not os.path.exists(ATTENDANCES_FILE):
    with open(ATTENDANCES_FILE, "w") as f:
        json.dump([], f)

# Rota para a página de login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cpf = request.form.get("cpf")
        password = request.form.get("password")
        print(f"Tentativa de login com CPF: {cpf}, Senha: {password}")  # Depuração
        if cpf in users and users[cpf]["password"] == password:
            session["user"] = cpf
            print("Login bem-sucedido, redirecionando para /scan")  # Depuração
            return redirect(url_for("scan"))
        else:
            print("Credenciais inválidas")  # Depuração
            rendered = render_template("login.html", error="Credenciais inválidas. Tente novamente.")
            print("Renderizando login.html (POST):", rendered[:500])  # Depuração
            return rendered
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
    print("Renderizando scan.html")  # Depuração
    return render_template("scan.html")

# Rota para registrar presença
@app.route("/register_attendance", methods=["POST"])
def register_attendance():
    if "user" not in session:
        print("Usuário não autenticado para registrar presença")  # Depuração
        return jsonify({"error": "Não autenticado"}), 401

    data = request.json
    qr_data = data.get("qr_data")
    print(f"Recebido QR code: {qr_data}")  # Depuração

    try:
        student_data = json.loads(qr_data)
        student_id = student_data.get("id")
        student_name = student_data.get("name")

        if student_id and student_name:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date = timestamp.split()[0]
            attendance_record = {
                "student_id": student_id,
                "student_name": student_name,
                "timestamp": timestamp,
                "date": date
            }
            # Carregar presenças existentes
            with open(ATTENDANCES_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    attendances = []
                else:
                    attendances = json.loads(content)
            # Adicionar nova presença
            attendances.append(attendance_record)
            # Salvar presenças atualizadas
            with open(ATTENDANCES_FILE, "w") as f:
                json.dump(attendances, f, indent=4)
            print(f"Presença registrada: {attendance_record}")  # Depuração
            return jsonify({"message": f"Presença registrada: {student_name} (ID: {student_id}) às {timestamp}"})
        else:
            print("Dados do aluno incompletos no QR code")  # Depuração
            return jsonify({"error": "Dados do aluno incompletos no QR code"}), 400
    except Exception as e:
        print(f"Erro ao registrar presença: {str(e)}")  # Depuração
        return jsonify({"error": f"Erro ao registrar presença: {str(e)}"}), 500

# Rota para visualizar presenças
@app.route("/attendances", methods=["GET"])
def view_attendances():
    if "user" not in session:
        print("Usuário não autenticado, redirecionando para login")  # Depuração
        return redirect(url_for("login"))
    
    try:
        print(f"Tentando ler o arquivo {ATTENDANCES_FILE}")  # Depuração
        with open(ATTENDANCES_FILE, "r") as f:
            content = f.read().strip()
            print(f"Conteúdo lido do arquivo: {content}")  # Depuração
            if not content:
                attendances = []
            else:
                attendances = json.loads(content)
        print(f"Presenças carregadas: {attendances}")  # Depuração
    except FileNotFoundError as e:
        print(f"Erro: Arquivo {ATTENDANCES_FILE} não encontrado: {str(e)}")  # Depuração
        attendances = []  # Retorna lista vazia se o arquivo não existir
    except json.JSONDecodeError as e:
        print(f"Erro: Falha ao decodificar o JSON em {ATTENDANCES_FILE}: {str(e)}")  # Depuração
        attendances = []  # Retorna lista vazia se o JSON for inválido
    except Exception as e:
        print(f"Erro inesperado ao ler {ATTENDANCES_FILE}: {str(e)}")  # Depuração
        return jsonify({"error": f"Erro ao carregar presenças: {str(e)}"}), 500

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