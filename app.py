from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import json
import logging
import traceback
from collections import Counter
from bcrypt import hashpw, gensalt, checkpw

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"  # Substitua por uma chave segura

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configuração do cliente Supabase
SUPABASE_URL = "https://trrhizrbbwnsgpcghasa.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRycmhpenJiYnduc2dwY2doYXNhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDM3MDQyMTcsImV4cCI6MjA1OTI4MDIxN30.3r6JHXbIpgILlsKg9j8LELTB4LCZHrIZsMi2HwCaVAM"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Teste inicial de conexão com Supabase
try:
    supabase.table("funcionarios").select("id").limit(1).execute()
    logger.info("Conexão com Supabase estabelecida com sucesso")
except Exception as e:
    logger.error(f"Falha ao conectar ao Supabase: {str(e)}")

# Função para limpar CPF
def clean_cpf(cpf):
    return ''.join(filter(str.isdigit, cpf))

# Rota para a página de login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json or request.form
        cpf = clean_cpf(data.get("cpf", ""))
        password = data.get("password", "")
        logger.info(f"Tentativa de login com CPF: {cpf}")

        try:
            response = supabase.table("funcionarios").select("*, polos!funcionarios_polo_id_fkey(nome)").eq("cpf", cpf).execute()
            logger.debug(f"Resposta do Supabase: {response.data}")
            user = response.data[0] if response.data else None

            if user:
                # Tentar verificar senha hasheada
                try:
                    if checkpw(password.encode('utf-8'), user["senha"].encode('utf-8')):
                        session["user"] = {
                            "id": user["id"],
                            "cpf": cpf,
                            "name": user["nome"],
                            "cargo": user["cargo"],
                            "polo_id": user.get("polo_id"),
                            "unidade": user.get("unidade"),
                            "polo_nome": user["polos"]["nome"] if user.get("polos") else "Desconhecido"
                        }
                        logger.info(f"Login bem-sucedido: {user['nome']}, redirecionando para /scan")
                        return jsonify({"message": "Login bem-sucedido", "redirect": url_for("scan")})
                except ValueError:
                    # Se a senha não for um hash válido, tentar comparação direta
                    if user["senha"] == password:
                        # Opcional: Atualizar para senha hasheada
                        hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
                        supabase.table("funcionarios").update({"senha": hashed_password}).eq("cpf", cpf).execute()
                        session["user"] = {
                            "id": user["id"],
                            "cpf": cpf,
                            "name": user["nome"],
                            "cargo": user["cargo"],
                            "polo_id": user.get("polo_id"),
                            "unidade": user.get("unidade"),
                            "polo_nome": user["polos"]["nome"] if user.get("polos") else "Desconhecido"
                        }
                        logger.info(f"Login bem-sucedido: {user['nome']}, redirecionando para /scan")
                        return jsonify({"message": "Login bem-sucedido", "redirect": url_for("scan")})

            logger.warning("Credenciais inválidas")
            if request.json:
                return jsonify({"error": "Credenciais inválidas. Tente novamente."}), 401
            return render_template("login.html", error="Credenciais inválidas. Tente novamente.")
        except Exception as e:
            error_msg = f"Erro ao conectar ao banco de dados: {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            if request.json:
                return jsonify({"error": error_msg}), 500
            return render_template("login.html", error=error_msg), 500

    return render_template("login.html", error=None)

# Rota para o dashboard
@app.route("/dashboard", methods=["GET"])
def dashboard():
    if "user" not in session:
        logger.warning("Usuário não autenticado, redirecionando para login")
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"])

@app.route("/api/dashboard_data", methods=["GET"])
def get_dashboard_data():
    if "user" not in session:
        logger.warning("Usuário não autenticado")
        return jsonify({"error": "Não autorizado"}), 401

    user = session["user"]
    try:
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        current_time = datetime.now(sao_paulo_tz)
        current_hour = current_time.hour
        current_period = 'manha' if 6 <= current_hour <= 12 else 'tarde'
        weekday_map = {0: 'seg', 1: 'ter', 2: 'qua', 3: 'qui', 4: 'sex', 5: 'sab', 6: 'dom'}
        current_weekday = weekday_map[current_time.weekday()]

        # Total de alunos
        query_alunos = supabase.table("alunos").select("id", count="exact")
        if user["cargo"] not in ["admin", "secretario"]:
            query_alunos = query_alunos.eq("polo_id", user["polo_id"])
        response_alunos = query_alunos.execute()
        total_alunos = response_alunos.count

        # Turmas ativas
        query_turmas = supabase.table("turmas").select(
            "id, nome, disciplinas!turmas_disciplina_id_fkey(tipo), matriculas!turmas_id_fkey(id)"
        )
        query_turmas = query_turmas.eq("periodo", current_period).eq("dia_semana", current_weekday)
        if user["cargo"] not in ["admin", "secretario"]:
            query_turmas = query_turmas.eq("polo_id", user["polo_id"])
        response_turmas = query_turmas.execute()
        turmas_ativas = [
            {
                "id": turma["id"],
                "nome": turma["nome"],
                "tipo": turma["disciplinas"]["tipo"] if turma.get("disciplinas") else None,
                "matriculas": len(turma["matriculas"]) if turma.get("matriculas") else 0
            }
            for turma in response_turmas.data
        ]
        total_turmas = len(turmas_ativas)
        cognitive_classes = len([t for t in turmas_ativas if t["tipo"] == "cognitiva"])
        motor_classes = len([t for t in turmas_ativas if t["tipo"] == "motora"])

        # Presenças recentes (últimas 5)
        query_presencas = supabase.table("presenca").select(
            "id, nome_aluno, data_escaneamento, turmas!presenca_turma_id_fkey(nome)"
        )
        query_presencas = query_presencas.order("data_escaneamento", desc=True).limit(5)
        if user["cargo"] not in ["admin", "secretario"]:
            turmas_polo = supabase.table("turmas").select("id").eq("polo_id", user["polo_id"]).execute()
            turmas_ids = [turma["id"] for turma in turmas_polo.data]
            if turmas_ids:
                query_presencas = query_presencas.in_("turma_id", turmas_ids)
            else:
                query_presencas = query_presencas.eq("turma_id", None)  # Evita erro se não houver turmas
        response_presencas = query_presencas.execute()
        presencas = [
            {
                "id": p["id"],
                "nome_aluno": p["nome_aluno"],
                "turma_nome": p["turmas"]["nome"] if p.get("turmas") else "Desconhecido",
                "data": p["data_escaneamento"]
            }
            for p in response_presencas.data
        ]

        # Presenças por dia (última semana)
        one_week_ago = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
        query_presencas_dias = supabase.table("presenca").select("data_escaneamento, turma_id")
        if user["cargo"] not in ["admin", "secretario"]:
            turmas_polo = supabase.table("turmas").select("id").eq("polo_id", user["polo_id"]).execute()
            turmas_ids = [turma["id"] for turma in turmas_polo.data]
            if turmas_ids:
                query_presencas_dias = query_presencas_dias.in_("turma_id", turmas_ids)
            else:
                query_presencas_dias = query_presencas_dias.eq("turma_id", None)
        query_presencas_dias = query_presencas_dias.gte("data_escaneamento", one_week_ago)
        response_presencas_dias = query_presencas_dias.execute()
        presencas_por_dia = Counter(p["data_escaneamento"] for p in response_presencas_dias.data if p["data_escaneamento"])

        return jsonify({
            "total_alunos": total_alunos,
            "total_turmas": total_turmas,
            "cognitive_classes": cognitive_classes,
            "motor_classes": motor_classes,
            "presencas": presencas,
            "presencas_por_dia": dict(presencas_por_dia),
            "current_period": current_period
        })
    except Exception as e:
        logger.error(f"Erro ao buscar dados do dashboard: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
# Rota para a página de leitura de QR code
@app.route("/scan", methods=["GET"])
def scan():
    if "user" not in session:
        logger.warning("Usuário não autenticado, redirecionando para login")
        return redirect(url_for("login"))

    user = session["user"]
    try:
        query = supabase.table("turmas").select(
            "id, nome, disciplinas!turmas_disciplina_id_fkey(nome, tipo), polos!turmas_polo_id_fkey(nome)"
        )

        if user["cargo"] in ["diretor", "monitor"]:
            response = supabase.table("funcionarios").select("unidade").eq("cpf", user["cpf"]).execute()
            unidade = response.data[0]["unidade"] if response.data else None
            if unidade:
                query = query.eq("unidade", unidade)
        elif user["cargo"] == "coordenador":
            response = supabase.table("funcionarios").select("polo_id").eq("cpf", user["cpf"]).execute()
            polo_id = response.data[0]["polo_id"] if response.data else None
            if polo_id:
                query = query.eq("polo_id", polo_id)

        response = query.execute()
        turmas = [
            {
                "id": turma["id"],
                "nome": turma["nome"],
                "disciplina": turma["disciplinas"]["nome"] if turma.get("disciplinas") else None,
                "tipo": turma["disciplinas"]["tipo"] if turma.get("disciplinas") else None,
                "polo": turma["polos"]["nome"] if turma.get("polos") else "Desconhecido",
                "unidade": turma.get("unidade")
            }
            for turma in response.data
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar turmas: {str(e)}")
        turmas = []

    logger.info("Renderizando scan.html")
    return render_template("scan.html", turmas=turmas, user=user)

# Rota para registrar presença
@app.route("/register_attendance", methods=["POST"])
def register_attendance():
    if "user" not in session:
        logger.warning("Usuário não autenticado para registrar presença")
        return jsonify({"error": "Não autenticado"}), 401

    data = request.json
    qr_data = data.get("qr_data")
    turma_id = data.get("turma_id")
    logger.info(f"Recebido QR code: {qr_data}, Turma ID: {turma_id}")

    try:
        student_id = qr_data
        if not student_id or not turma_id:
            logger.warning("Dados incompletos no QR code ou turma não selecionada")
            return jsonify({"error": "Dados incompletos no QR code ou turma não selecionada"}), 400

        response = supabase.table("alunos").select("*").eq("id", student_id).execute()
        student = response.data[0] if response.data else None
        if not student:
            logger.warning("Aluno não encontrado")
            return jsonify({"error": "Aluno não encontrado"}), 404

        student_name = student["nome"]
        # Buscar o matriculas.id para este aluno e turma
        response = supabase.table("matriculas").select("id").eq("aluno_id", student_id).eq("turma_id", turma_id).execute()
        matricula = response.data[0]["id"] if response.data else None
        if not matricula:
            logger.warning("Aluno não está matriculado nesta turma")
            return jsonify({"error": "Aluno não está matriculado nesta turma"}), 403

        today = datetime.now().strftime("%Y-%m-%d")
        response = supabase.table("presenca").select("*").eq("id_aluno", student_id).eq("turma_id", turma_id).eq("data_escaneamento", today).execute()
        if response.data:
            logger.warning("Presença já registrada para esta aula hoje")
            return jsonify({"error": "Presença já registrada para esta aula hoje"}), 400

        timestamp = datetime.now()
        response = supabase.table("presenca").insert({
            "id_aluno": student_id,
            "matricula": matricula,  # Usa matriculas.id (uuid)
            "nome_aluno": student_name,
            "unidade": student["unidade"],
            "etapa": student["etapa"],
            "turma_id": turma_id,
            "turno_escola_viva": student["turno"],
            "timestamp": timestamp.isoformat(),
            "presenca": "presente",
            "data_escaneamento": timestamp.strftime("%Y-%m-%d"),
            "hora_escaneamento": timestamp.strftime("%H:%M:%S")
        }).execute()

        logger.info(f"Presença registrada: {student_name} (ID: {student_id}) às {timestamp}")
        return jsonify({"message": f"Presença registrada: {student_name} (ID: {student_id}) às {timestamp}"})
    except Exception as e:
        logger.error(f"Erro ao registrar presença: {str(e)}")
        return jsonify({"error": f"Erro ao registrar presença: {str(e)}"}), 500

# Rota para visualizar presenças
@app.route("/attendances", methods=["GET"])
def view_attendances():
    if "user" not in session:
        logger.warning("Usuário não autenticado, redirecionando para login")
        return redirect(url_for("login"))

    user = session["user"]
    try:
        query = supabase.table("presenca").select(
            "*, alunos!presenca_id_aluno_fkey(nome, matricula), turmas!presenca_turma_id_fkey(nome, disciplinas!turmas_disciplina_id_fkey(nome, tipo), polos!turmas_polo_id_fkey(id))"
        )

        if user["cargo"] in ["diretor", "monitor"]:
            response = supabase.table("funcionarios").select("unidade").eq("cpf", user["cpf"]).execute()
            unidade = response.data[0]["unidade"] if response.data else None
            if unidade:
                query = query.eq("unidade", unidade)
        elif user["cargo"] == "coordenador":
            response = supabase.table("funcionarios").select("polo_id").eq("cpf", user["cpf"]).execute()
            polo_id = response.data[0]["polo_id"] if response.data else None
            if polo_id:
                query = query.eq("turmas.polo_id", polo_id)

        response = query.order("timestamp", desc=True).execute()
        attendances = [
            {
                "student_id": row["id_aluno"],
                "student_name": row["alunos"]["nome"] if row.get("alunos") else "Desconhecido",
                "matricula": row["alunos"]["matricula"] if row.get("alunos") else None,
                "turma_nome": row["turmas"]["nome"] if row.get("turmas") else "Desconhecido",
                "disciplina": row["turmas"]["disciplinas"]["nome"] if row.get("turmas", {}).get("disciplinas") else None,
                "disciplina_tipo": row["turmas"]["disciplinas"]["tipo"] if row.get("turmas", {}).get("disciplinas") else None,
                "timestamp": datetime.fromisoformat(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S") if row["timestamp"] else None,
                "date": row["data_escaneamento"]
            }
            for row in response.data
        ]
    except Exception as e:
        logger.error(f"Erro ao buscar presenças: {str(e)}")
        attendances = []

    logger.info("Renderizando attendances.html")
    return render_template("attendances.html", attendances=attendances, user=user)

@app.route("/register", methods=["POST"])
def register():
    data = request.json or request.form
    cpf = clean_cpf(data.get("cpf", ""))
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    polo_id = data.get("poloId", "").strip()
    password = data.get("password", "")
    confirm_password = data.get("confirmPassword", "")

    logger.info(f"Tentativa de cadastro com CPF: {cpf}, E-mail: {email}, Polo ID: {polo_id}")

    try:
        # Validações
        if not cpf or len(cpf) != 11:
            logger.warning("CPF inválido")
            return jsonify({"error": "CPF inválido. Deve conter 11 dígitos."}), 400

        if not name or len(name) < 2:
            logger.warning("Nome inválido")
            return jsonify({"error": "Nome inválido. Deve conter pelo menos 2 caracteres."}), 400

        if not email or not "@" in email or not "." in email:
            logger.warning("E-mail inválido")
            return jsonify({"error": "E-mail inválido."}), 400

        if not polo_id:
            logger.warning("Polo não selecionado")
            return jsonify({"error": "Por favor, selecione um polo."}), 400

        # Verificar se o polo existe
        response_polo = supabase.table("polos").select("id").eq("id", polo_id).execute()
        if not response_polo.data:
            logger.warning("Polo inválido")
            return jsonify({"error": "Polo selecionado é inválido."}), 400

        if not password or len(password) < 6:
            logger.warning("Senha inválida")
            return jsonify({"error": "A senha deve ter pelo menos 6 caracteres."}), 400

        if password != confirm_password:
            logger.warning("Senhas não coincidem")
            return jsonify({"error": "As senhas não coincidem."}), 400

        # Verificar se CPF ou e-mail já existem
        response_cpf = supabase.table("funcionarios").select("cpf").eq("cpf", cpf).execute()
        if response_cpf.data:
            logger.warning("CPF já registrado")
            return jsonify({"error": "Este CPF já está registrado."}), 400

        response_email = supabase.table("funcionarios").select("email").eq("email", email).execute()
        if response_email.data:
            logger.warning("E-mail já registrado")
            return jsonify({"error": "Este e-mail já está registrado."}), 400

        # Hash da senha
        hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')

        # Inserir novo usuário
        new_user = {
            "cpf": cpf,
            "nome": name,
            "email": email,
            "senha": hashed_password,
            "cargo": "monitor",
            "polo_id": polo_id,
            "unidade": None
        }
        response = supabase.table("funcionarios").insert(new_user).execute()

        if response.data:
            logger.info(f"Usuário cadastrado com sucesso: {name}")
            return jsonify({"message": "Cadastro realizado com sucesso!"}), 200
        else:
            logger.error("Falha ao inserir usuário no Supabase")
            return jsonify({"error": "Erro ao realizar cadastro. Tente novamente."}), 500

    except Exception as e:
        error_msg = f"Erro ao processar cadastro: {str(e)}"
        logger.error(error_msg)
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

@app.route("/forgot_password", methods=["POST"])
def forgot_password():
    data = request.json or request.form
    cpf = clean_cpf(data.get("cpf", ""))
    new_password = data.get("newPassword", "")
    confirm_password = data.get("confirmPassword", "")

    logger.info(f"Tentativa de redefinição de senha com CPF: {cpf}")

    try:
        # Validações
        if not cpf or len(cpf) != 11:
            logger.warning("CPF inválido")
            return jsonify({"error": "CPF inválido. Deve conter 11 dígitos."}), 400

        if not new_password or len(new_password) < 6:
            logger.warning("Senha inválida")
            return jsonify({"error": "A nova senha deve ter pelo menos 6 caracteres."}), 400

        if new_password != confirm_password:
            logger.warning("Senhas não coincidem")
            return jsonify({"error": "As senhas não coincidem."}), 400

        # Verificar se o CPF existe
        response = supabase.table("funcionarios").select("cpf").eq("cpf", cpf).execute()
        if not response.data:
            logger.warning("CPF não encontrado")
            return jsonify({"error": "CPF não encontrado."}), 404

        # Hash da nova senha
        hashed_password = hashpw(new_password.encode('utf-8'), gensalt()).decode('utf-8')

        # Atualizar a senha no banco
        response = supabase.table("funcionarios").update({"senha": hashed_password}).eq("cpf", cpf).execute()

        if response.data:
            logger.info(f"Senha redefinida com sucesso para CPF: {cpf}")
            return jsonify({"message": "Senha redefinida com sucesso!"}), 200
        else:
            logger.error("Falha ao atualizar senha no Supabase")
            return jsonify({"error": "Erro ao redefinir senha. Tente novamente."}), 500

    except Exception as e:
        error_msg = f"Erro ao processar redefinição de senha: {str(e)}"
        logger.error(error_msg)
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

@app.route("/api/polos", methods=["GET"])
def get_polos():
    try:
        response = supabase.table("polos").select("id, nome").execute()
        logger.info("Polos buscados com sucesso")
        return jsonify(response.data), 200
    except Exception as e:
        error_msg = f"Erro ao buscar polos: {str(e)}"
        logger.error(error_msg)
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

# Rota para logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    logger.info("Usuário fez logout, redirecionando para login")
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
    app.run(debug=True, host="0.0.0.0", port=5000)