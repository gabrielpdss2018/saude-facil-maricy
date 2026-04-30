from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import uuid
from datetime import date
import os

app = Flask(__name__)
app.secret_key = 'chave_secreta_saude_facil'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description): d[col[0]] = row[idx]
    return d

def get_conexao():
    conexao = sqlite3.connect('saude_facil.db')
    conexao.row_factory = dict_factory
    return conexao

# ================= AUTO-CONFIGURAÇÃO DO BANCO =================
# Essa função roda sozinha quando o servidor liga e cria todas as tabelas!
def auto_setup_bd():
    conexao = sqlite3.connect('saude_facil.db')
    cursor = conexao.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuario (id INTEGER PRIMARY KEY AUTOINCREMENT, cpf TEXT UNIQUE NOT NULL, cartao_sus TEXT UNIQUE NOT NULL, nome TEXT NOT NULL, nome_social TEXT, email TEXT, telefone TEXT, senha TEXT NOT NULL, cep TEXT, logradouro TEXT, numero TEXT, complemento TEXT, bairro TEXT, cidade TEXT, uf TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ubs (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, endereco TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS servico_saude (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, descricao TEXT, icone TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ubs_servico (ubs_id INTEGER, servico_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS profissional (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, cargo TEXT NOT NULL, login TEXT UNIQUE NOT NULL, senha TEXT NOT NULL, ubs_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS gestor (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, login TEXT UNIQUE NOT NULL, senha TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS agendamento (protocolo TEXT PRIMARY KEY, usuario_id INTEGER, ubs_id INTEGER, servico_id INTEGER, data_atendimento DATE NOT NULL, horario_atendimento TIME NOT NULL, status TEXT DEFAULT 'PENDENTE', observacoes_medicas TEXT)''')
    
    admin = cursor.execute("SELECT * FROM gestor WHERE login='gestor.admin'").fetchone()
    if not admin:
        cursor.execute("INSERT INTO gestor (nome, login, senha) VALUES ('Secretaria de Saúde', 'gestor.admin', 'admin123')")
        cursor.executemany("INSERT INTO ubs (id, nome, endereco) VALUES (?, ?, ?)", [(1, 'UBS Central', 'Rua Principal, 100'), (2, 'UBS Bairro Novo', 'Av. das Árvores, 200')])
        cursor.executemany("INSERT INTO servico_saude (id, nome, descricao, icone) VALUES (?, ?, ?, ?)", [(1, 'Clínico Geral', 'Consulta de rotina', 'fa-user-doctor'), (2, 'Odontologia', 'Avaliação e limpeza', 'fa-tooth'), (3, 'Enfermagem', 'Triagem e curativos', 'fa-user-nurse'), (4, 'Vacinação', 'Campanhas e rotina', 'fa-syringe')])
        cursor.executemany("INSERT INTO ubs_servico (ubs_id, servico_id) VALUES (?, ?)", [(1,1), (1,2), (1,3), (1,4), (2,1), (2,4)])
        cursor.executemany("INSERT INTO profissional (id, nome, cargo, login, senha, ubs_id) VALUES (?, ?, ?, ?, ?, ?)", [(1, 'Dra. Ana Silva', 'Médica', 'ana.med', 'senha123', 1)])
    conexao.commit()
    conexao.close()

# Roda a verificação antes da primeira requisição
with app.app_context():
    auto_setup_bd()

# ================= ROTAS DO CIDADÃO =================
@app.route('/')
def home(): return render_template('index.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    erro = None
    if request.method == 'POST':
        conexao = get_conexao()
        try:
            conexao.execute('INSERT INTO usuario (cpf, cartao_sus, nome, nome_social, senha) VALUES (?, ?, ?, ?, ?)', 
                            (request.form['cpf'], request.form['cartao_sus'], request.form['nome'], request.form['nome_social'], request.form['senha']))
            conexao.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError: erro = "CPF ou Cartão SUS já cadastrado!"
        finally: conexao.close()
    return render_template('registro.html', erro=erro)

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        conexao = get_conexao()
        usuario = conexao.execute('SELECT * FROM usuario WHERE (cpf = ? OR cartao_sus = ?) AND senha = ?', (request.form['cpf_sus'], request.form['cpf_sus'], request.form['senha'])).fetchone()
        conexao.close()
        if usuario:
            session['usuario_id'] = usuario['id']
            session['nome_exibicao'] = usuario.get('nome_social') if usuario.get('nome_social') else usuario['nome'].split()[0]
            return redirect(url_for('agendamento'))
        else: erro = "Credenciais inválidas."
    return render_template('login.html', erro=erro)

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao()
    mensagem = None
    if request.method == 'POST':
        conexao.execute('''UPDATE usuario SET nome_social=?, email=?, telefone=?, cep=?, logradouro=?, numero=?, complemento=?, bairro=?, cidade=?, uf=? WHERE id=?''', 
                        (request.form['nome_social'], request.form['email'], request.form['telefone'], request.form['cep'], request.form['logradouro'], request.form['numero'], request.form['complemento'], request.form['bairro'], request.form['cidade'], request.form['uf'], session['usuario_id']))
        conexao.commit()
        if request.form['nome_social'].strip() != "": session['nome_exibicao'] = request.form['nome_social']
        mensagem = "Perfil atualizado!"
    usuario = conexao.execute('SELECT * FROM usuario WHERE id = ?', (session['usuario_id'],)).fetchone()
    conexao.close()
    return render_template('perfil.html', usuario=usuario, nome=session['nome_exibicao'], mensagem=mensagem)

@app.route('/agendamento', methods=['GET', 'POST'])
def agendamento():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao()
    if request.method == 'POST':
        protocolo = str(uuid.uuid4())[:8].upper()
        conexao.execute('''INSERT INTO agendamento (protocolo, usuario_id, ubs_id, servico_id, data_atendimento, horario_atendimento) VALUES (?, ?, ?, ?, ?, ?)''', 
                        (protocolo, session['usuario_id'], request.form['ubs_id'], request.form['servico_id'], request.form['data'], request.form['horario']))
        conexao.commit()
        conexao.close()
        return render_template('sucesso.html', protocolo=protocolo, data=request.form['data'], horario=request.form['horario'], nome=session['nome_exibicao'])
    lista_ubs = conexao.execute('SELECT * FROM ubs').fetchall()
    conexao.close()
    return render_template('agendamento.html', ubs=lista_ubs, nome=session['nome_exibicao'])

@app.route('/api/servicos_por_ubs/<int:ubs_id>')
def api_servicos_por_ubs(ubs_id):
    conexao = get_conexao()
    servicos = conexao.execute('SELECT s.* FROM servico_saude s JOIN ubs_servico us ON s.id = us.servico_id WHERE us.ubs_id = ?', (ubs_id,)).fetchall()
    conexao.close()
    return jsonify(servicos)

@app.route('/api/horarios', methods=['POST'])
def api_horarios():
    dados = request.json
    horarios_base = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(8, 18) for m in (0, 30)]
    horarios_base = [h for h in horarios_base if h <= '17:00']
    conexao = get_conexao()
    agendados = conexao.execute("SELECT horario_atendimento FROM agendamento WHERE data_atendimento = ? AND ubs_id = ? AND status != 'CANCELADO'", (dados.get('data'), dados.get('ubs_id'))).fetchall()
    conexao.close()
    horarios_ocupados = [a['horario_atendimento'] for a in agendados]
    horarios_livres = [h for h in horarios_base if h not in horarios_ocupados]
    return jsonify({"horarios": horarios_livres, "vagas": len(horarios_livres)})

@app.route('/meus_agendamentos')
def meus_agendamentos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao()
    agendamentos = conexao.execute('''SELECT a.*, u.nome as ubs_nome, s.nome as servico_nome FROM agendamento a JOIN ubs u ON a.ubs_id = u.id JOIN servico_saude s ON a.servico_id = s.id WHERE a.usuario_id = ? ORDER BY a.data_atendimento DESC, a.horario_atendimento DESC''', (session['usuario_id'],)).fetchall()
    conexao.close()
    return render_template('meus_agendamentos.html', agendamentos=agendamentos, nome=session['nome_exibicao'])

@app.route('/api/calendario_usuario')
def api_calendario_usuario():
    if 'usuario_id' not in session: return jsonify([])
    conexao = get_conexao()
    agendamentos = conexao.execute("SELECT a.*, u.nome as ubs_nome, s.nome as servico_nome FROM agendamento a JOIN ubs u ON a.ubs_id = u.id JOIN servico_saude s ON a.servico_id = s.id WHERE a.usuario_id = ?", (session['usuario_id'],)).fetchall()
    conexao.close()
    eventos = []
    for a in agendamentos:
        cor = "#f39c12"
        if a['status'] == 'FINALIZADO': cor = "#27ae60"
        elif a['status'] == 'CANCELADO': cor = "#e74c3c"
        eventos.append({"id": a['protocolo'], "title": a['servico_nome'], "start": f"{a['data_atendimento']}T{a['horario_atendimento']}", "color": cor, "extendedProps": {"ubs": a['ubs_nome'], "status": a['status'], "protocolo": a['protocolo']}})
    return jsonify(eventos)

@app.route('/cancelar/<protocolo>')
def cancelar_agendamento(protocolo):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao()
    conexao.execute('UPDATE agendamento SET status = "CANCELADO" WHERE protocolo = ? AND usuario_id = ?', (protocolo, session['usuario_id']))
    conexao.commit()
    conexao.close()
    return redirect(url_for('meus_agendamentos'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ================= ROTAS DO PROFISSIONAL / UBS =================
@app.route('/login_servidor', methods=['GET', 'POST'])
def login_servidor():
    erro = None
    if request.method == 'POST':
        conexao = get_conexao()
        profissional = conexao.execute('SELECT p.*, u.nome as ubs_nome FROM profissional p JOIN ubs u ON p.ubs_id = u.id WHERE p.login = ? AND p.senha = ?', (request.form['login'], request.form['senha'])).fetchone()
        conexao.close()
        if profissional:
            session['profissional_id'] = profissional['id']; session['profissional_nome'] = profissional['nome']; session['profissional_ubs_id'] = profissional['ubs_id']; session['profissional_ubs_nome'] = profissional['ubs_nome']
            return redirect(url_for('painel_profissional'))
        else: erro = "Credenciais incorretas."
    return render_template('login_servidor.html', erro=erro)

@app.route('/painel_profissional')
def painel_profissional():
    if 'profissional_id' not in session: return redirect(url_for('login_servidor'))
    conexao = get_conexao()
    hoje = date.today().strftime('%Y-%m-%d')
    pacientes = conexao.execute('''SELECT a.*, u.nome as paciente_nome, u.cpf as paciente_cpf, s.nome as servico_nome FROM agendamento a JOIN usuario u ON a.usuario_id = u.id JOIN servico_saude s ON a.servico_id = s.id WHERE a.ubs_id = ? AND a.data_atendimento = ? ORDER BY a.horario_atendimento ASC''', (session['profissional_ubs_id'], hoje)).fetchall()
    conexao.close()
    return render_template('painel_profissional.html', pacientes=pacientes, nome=session['profissional_nome'], ubs=session['profissional_ubs_nome'], hoje=hoje)

@app.route('/atualizar_status/<protocolo>', methods=['POST'])
def atualizar_status(protocolo):
    if 'profissional_id' not in session: return redirect(url_for('login_servidor'))
    conexao = get_conexao()
    conexao.execute('UPDATE agendamento SET status = ?, observacoes_medicas = ? WHERE protocolo = ? AND ubs_id = ?', (request.form['status'], request.form.get('observacoes', ''), protocolo, session['profissional_ubs_id']))
    conexao.commit()
    conexao.close()
    return redirect(url_for('painel_profissional'))

@app.route('/logout_servidor')
def logout_servidor():
    session.pop('profissional_id', None); session.pop('profissional_nome', None); session.pop('profissional_ubs_id', None); session.pop('profissional_ubs_nome', None)
    return redirect(url_for('login_servidor'))

# ================= ROTAS DO GESTOR MUNICIPAL =================
@app.route('/login_gestor', methods=['GET', 'POST'])
def login_gestor():
    erro = None
    if request.method == 'POST':
        conexao = get_conexao()
        gestor = conexao.execute('SELECT * FROM gestor WHERE login = ? AND senha = ?', (request.form['login'], request.form['senha'])).fetchone()
        conexao.close()
        if gestor:
            session['gestor_id'] = gestor['id']; session['gestor_nome'] = gestor['nome']
            return redirect(url_for('painel_gestor'))
        else: erro = "Credenciais incorretas."
    return render_template('login_gestor.html', erro=erro)

@app.route('/painel_gestor')
def painel_gestor():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    conexao = get_conexao()
    total = conexao.execute('SELECT COUNT(*) as qtd FROM agendamento').fetchone()['qtd']
    finalizados = conexao.execute('SELECT COUNT(*) as qtd FROM agendamento WHERE status="FINALIZADO"').fetchone()['qtd']
    cancelados = conexao.execute('SELECT COUNT(*) as qtd FROM agendamento WHERE status="CANCELADO"').fetchone()['qtd']
    relatorio_ubs = conexao.execute('''SELECT u.nome as ubs_nome, COUNT(a.protocolo) as total, SUM(CASE WHEN a.status = 'FINALIZADO' THEN 1 ELSE 0 END) as concluidos, SUM(CASE WHEN a.status = 'CANCELADO' THEN 1 ELSE 0 END) as faltas FROM ubs u LEFT JOIN agendamento a ON u.id = a.ubs_id GROUP BY u.id''').fetchall()
    conexao.close()
    return render_template('painel_gestor.html', nome=session['gestor_nome'], total=total, finalizados=finalizados, cancelados=cancelados, relatorio_ubs=relatorio_ubs)

@app.route('/cadastrar_ubs', methods=['GET', 'POST'])
def cadastrar_ubs():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    mensagem = None
    conexao = get_conexao()
    if request.method == 'POST':
        cursor = conexao.cursor()
        cursor.execute('INSERT INTO ubs (nome, endereco) VALUES (?, ?)', (request.form['nome'], request.form['endereco']))
        ubs_id = cursor.lastrowid
        for servico_id in request.form.getlist('servicos'):
            cursor.execute('INSERT INTO ubs_servico (ubs_id, servico_id) VALUES (?, ?)', (ubs_id, servico_id))
        conexao.commit()
        mensagem = f"Unidade '{request.form['nome']}' cadastrada com sucesso!"
    todos_servicos = conexao.execute('SELECT * FROM servico_saude').fetchall()
    conexao.close()
    return render_template('cadastrar_ubs.html', nome=session['gestor_nome'], servicos=todos_servicos, mensagem=mensagem)

# NOVA ROTA: CADASTRAR SERVIÇOS DO CATÁLOGO!
@app.route('/cadastrar_servico', methods=['GET', 'POST'])
def cadastrar_servico():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    mensagem = None
    if request.method == 'POST':
        conexao = get_conexao()
        conexao.execute('INSERT INTO servico_saude (nome, descricao, icone) VALUES (?, ?, ?)', 
                        (request.form['nome'], request.form['descricao'], request.form['icone']))
        conexao.commit()
        conexao.close()
        mensagem = "Novo Serviço adicionado ao catálogo geral da Prefeitura!"
    return render_template('cadastrar_servico.html', nome=session['gestor_nome'], mensagem=mensagem)

@app.route('/cadastrar_profissional', methods=['GET', 'POST'])
def cadastrar_profissional():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    mensagem = None; erro = None
    conexao = get_conexao()
    if request.method == 'POST':
        try:
            conexao.execute('INSERT INTO profissional (nome, cargo, login, senha, ubs_id) VALUES (?, ?, ?, ?, ?)', 
                            (request.form['nome'], request.form['cargo'], request.form['login'], request.form['senha'], request.form['ubs_id']))
            conexao.commit()
            mensagem = "Profissional cadastrado com sucesso!"
        except sqlite3.IntegrityError: erro = "Este Login/Matrícula já está em uso."
    lista_ubs = conexao.execute('SELECT * FROM ubs ORDER BY nome').fetchall()
    conexao.close()
    return render_template('cadastrar_profissional.html', nome=session['gestor_nome'], ubs=lista_ubs, mensagem=mensagem, erro=erro)

@app.route('/logout_gestor')
def logout_gestor():
    session.pop('gestor_id', None); session.pop('gestor_nome', None)
    return redirect(url_for('login_gestor'))

if __name__ == '__main__':
    app.run(debug=True)