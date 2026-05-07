from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import uuid
from datetime import date

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

with app.app_context():
    auto_setup_bd()

# ================= ROTAS DE REAGENDAMENTO (NOVAS) =================

@app.route('/reagendar/<protocolo>', methods=['GET', 'POST'])
def reagendar(protocolo):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao()
    
    # Busca dados atuais do agendamento
    agendamento_atual = conexao.execute('''
        SELECT a.*, u.nome as ubs_nome, s.nome as servico_nome 
        FROM agendamento a 
        JOIN ubs u ON a.ubs_id = u.id 
        JOIN servico_saude s ON a.servico_id = s.id 
        WHERE a.protocolo = ? AND a.usuario_id = ?
    ''', (protocolo, session['usuario_id'])).fetchone()

    if request.method == 'POST':
        nova_data = request.form['data']
        novo_horario = request.form['horario']
        
        # Atualiza para novo horário e volta status para PENDENTE
        conexao.execute('''
            UPDATE agendamento 
            SET data_atendimento = ?, horario_atendimento = ?, status = 'PENDENTE' 
            WHERE protocolo = ?
        ''', (nova_data, novo_horario, protocolo))
        conexao.commit()
        conexao.close()
        return redirect(url_for('meus_agendamentos'))

    conexao.close()
    return render_template('reagendar.html', a=agendamento_atual, nome=session['nome_exibicao'])

@app.route('/solicitar_reagendamento/<protocolo>', methods=['POST'])
def solicitar_reagendamento(protocolo):
    if 'profissional_id' not in session: return redirect(url_for('login_servidor'))
    
    conexao = get_conexao()
    # Profissional marca que a consulta precisa de nova data (Indisponibilidade - RF08)
    conexao.execute('''
        UPDATE agendamento 
        SET status = 'REAGENDAMENTO SOLICITADO' 
        WHERE protocolo = ? AND ubs_id = ?
    ''', (protocolo, session['profissional_ubs_id']))
    conexao.commit()
    conexao.close()
    return redirect(url_for('painel_profissional'))

# ================= ROTA DE RECUPERAÇÃO DE SENHA =================
@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    tipo = request.args.get('tipo', 'cidadao')
    erro = None; mensagem = None
    if request.method == 'POST':
        identificador = request.form['identificador']; nova_senha = request.form['nova_senha']; tipo = request.form['tipo']
        conexao = get_conexao()
        if tipo == 'cidadao':
            u = conexao.execute('SELECT id FROM usuario WHERE cpf=? OR cartao_sus=?', (identificador, identificador)).fetchone()
            if u: conexao.execute('UPDATE usuario SET senha=? WHERE id=?', (nova_senha, u['id']))
            else: erro = "Cidadão não encontrado."
        elif tipo == 'servidor':
            p = conexao.execute('SELECT id FROM profissional WHERE login=?', (identificador,)).fetchone()
            if p: conexao.execute('UPDATE profissional SET senha=? WHERE id=?', (nova_senha, p['id']))
            else: erro = "Servidor não encontrado."
        elif tipo == 'gestor':
            g = conexao.execute('SELECT id FROM gestor WHERE login=?', (identificador,)).fetchone()
            if g: conexao.execute('UPDATE gestor SET senha=? WHERE id=?', (nova_senha, g['id']))
            else: erro = "Gestor não encontrado."
        if not erro: conexao.commit(); mensagem = "Senha alterada!"
        conexao.close()
    return render_template('recuperar_senha.html', tipo=tipo, erro=erro, mensagem=mensagem)

# ================= ROTAS PADRÃO (MANTIDAS) =================
@app.route('/')
def home(): return render_template('index.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    erro = None
    if request.method == 'POST':
        conexao = get_conexao()
        try:
            conexao.execute('INSERT INTO usuario (cpf, cartao_sus, nome, nome_social, senha) VALUES (?, ?, ?, ?, ?)', (request.form['cpf'], request.form['cartao_sus'], request.form['nome'], request.form['nome_social'], request.form['senha']))
            conexao.commit(); return redirect(url_for('login'))
        except sqlite3.IntegrityError: erro = "CPF/SUS já cadastrado!"
        finally: conexao.close()
    return render_template('registro.html', erro=erro)

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        conexao = get_conexao(); u = conexao.execute('SELECT * FROM usuario WHERE (cpf=? OR cartao_sus=?) AND senha=?', (request.form['cpf_sus'], request.form['cpf_sus'], request.form['senha'])).fetchone(); conexao.close()
        if u:
            session['usuario_id'] = u['id']; session['nome_exibicao'] = u.get('nome_social') if u.get('nome_social') else u['nome'].split()[0]
            return redirect(url_for('agendamento'))
        else: erro = "Dados inválidos."
    return render_template('login.html', erro=erro)

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao(); m = None
    if request.method == 'POST':
        conexao.execute('''UPDATE usuario SET nome_social=?, email=?, telefone=?, cep=?, logradouro=?, numero=?, complemento=?, bairro=?, cidade=?, uf=? WHERE id=?''', (request.form['nome_social'], request.form['email'], request.form['telefone'], request.form['cep'], request.form['logradouro'], request.form['numero'], request.form['complemento'], request.form['bairro'], request.form['cidade'], request.form['uf'], session['usuario_id']))
        conexao.commit(); m = "Perfil atualizado!"
    u = conexao.execute('SELECT * FROM usuario WHERE id=?', (session['usuario_id'],)).fetchone(); conexao.close()
    return render_template('perfil.html', usuario=u, nome=session['nome_exibicao'], mensagem=m)

@app.route('/agendamento', methods=['GET', 'POST'])
def agendamento():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao()
    if request.method == 'POST':
        p = str(uuid.uuid4())[:8].upper()
        conexao.execute('''INSERT INTO agendamento (protocolo, usuario_id, ubs_id, servico_id, data_atendimento, horario_atendimento) VALUES (?, ?, ?, ?, ?, ?)''', (p, session['usuario_id'], request.form['ubs_id'], request.form['servico_id'], request.form['data'], request.form['horario']))
        conexao.commit(); conexao.close(); return render_template('sucesso.html', protocolo=p, data=request.form['data'], horario=request.form['horario'], nome=session['nome_exibicao'])
    ubs = conexao.execute('SELECT * FROM ubs').fetchall(); conexao.close()
    return render_template('agendamento.html', ubs=ubs, nome=session['nome_exibicao'])

@app.route('/api/servicos_por_ubs/<int:ubs_id>')
def api_servicos_por_ubs(ubs_id):
    conexao = get_conexao(); s = conexao.execute('SELECT s.* FROM servico_saude s JOIN ubs_servico us ON s.id = us.servico_id WHERE us.ubs_id = ?', (ubs_id,)).fetchall(); conexao.close()
    return jsonify(s)

@app.route('/api/horarios', methods=['POST'])
def api_horarios():
    dados = request.json
    h_base = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(8, 18) for m in (0, 30)]
    h_base = [h for h in h_base if h <= '17:00']
    conexao = get_conexao(); a = conexao.execute("SELECT horario_atendimento FROM agendamento WHERE data_atendimento=? AND ubs_id=? AND status!='CANCELADO'", (dados.get('data'), dados.get('ubs_id'))).fetchall(); conexao.close()
    h_ocu = [i['horario_atendimento'] for i in a]; h_liv = [h for h in h_base if h not in h_ocu]
    return jsonify({"horarios": h_liv, "vagas": len(h_liv)})

@app.route('/meus_agendamentos')
def meus_agendamentos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao(); a = conexao.execute('''SELECT a.*, u.nome as ubs_nome, s.nome as servico_nome FROM agendamento a JOIN ubs u ON a.ubs_id = u.id JOIN servico_saude s ON a.servico_id = s.id WHERE a.usuario_id = ? ORDER BY a.data_atendimento DESC, a.horario_atendimento DESC''', (session['usuario_id'],)).fetchall(); conexao.close()
    return render_template('meus_agendamentos.html', agendamentos=a, nome=session['nome_exibicao'])

@app.route('/api/calendario_usuario')
def api_calendario_usuario():
    if 'usuario_id' not in session: return jsonify([])
    conexao = get_conexao(); a = conexao.execute("SELECT a.*, u.nome as ubs_nome, s.nome as servico_nome FROM agendamento a JOIN ubs u ON a.ubs_id = u.id JOIN servico_saude s ON a.servico_id = s.id WHERE a.usuario_id = ?", (session['usuario_id'],)).fetchall(); conexao.close()
    ev = []
    for i in a:
        c = "#f39c12"
        if i['status'] == 'FINALIZADO': c = "#27ae60"
        elif i['status'] in ['CANCELADO', 'REAGENDAMENTO SOLICITADO']: c = "#e74c3c"
        ev.append({"id": i['protocolo'], "title": i['servico_nome'], "start": f"{i['data_atendimento']}T{i['horario_atendimento']}", "color": c, "extendedProps": {"ubs": i['ubs_nome'], "status": i['status'], "protocolo": i['protocolo']}})
    return jsonify(ev)

@app.route('/cancelar/<protocolo>')
def cancelar_agendamento(protocolo):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conexao = get_conexao(); conexao.execute('UPDATE agendamento SET status="CANCELADO" WHERE protocolo=? AND usuario_id=?', (protocolo, session['usuario_id'])); conexao.commit(); conexao.close(); return redirect(url_for('meus_agendamentos'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/login_servidor', methods=['GET', 'POST'])
def login_servidor():
    e = None
    if request.method == 'POST':
        conexao = get_conexao(); p = conexao.execute('SELECT p.*, u.nome as ubs_nome FROM profissional p JOIN ubs u ON p.ubs_id = u.id WHERE p.login = ? AND p.senha = ?', (request.form['login'], request.form['senha'])).fetchone(); conexao.close()
        if p: session['profissional_id']=p['id']; session['profissional_nome']=p['nome']; session['profissional_ubs_id']=p['ubs_id']; session['profissional_ubs_nome']=p['ubs_nome']; return redirect(url_for('painel_profissional'))
        else: e = "Credenciais incorretas."
    return render_template('login_servidor.html', erro=e)

@app.route('/painel_profissional')
def painel_profissional():
    if 'profissional_id' not in session: return redirect(url_for('login_servidor'))
    conexao = get_conexao(); h = date.today().strftime('%Y-%m-%d'); p = conexao.execute('''SELECT a.*, u.nome as paciente_nome, u.cpf as paciente_cpf, s.nome as servico_nome FROM agendamento a JOIN usuario u ON a.usuario_id = u.id JOIN servico_saude s ON a.servico_id = s.id WHERE a.ubs_id = ? AND a.data_atendimento = ? ORDER BY a.horario_atendimento ASC''', (session['profissional_ubs_id'], h)).fetchall(); conexao.close()
    return render_template('painel_profissional.html', pacientes=p, nome=session['profissional_nome'], ubs=session['profissional_ubs_nome'], hoje=h)

@app.route('/atualizar_status/<protocolo>', methods=['POST'])
def atualizar_status(protocolo):
    if 'profissional_id' not in session: return redirect(url_for('login_servidor'))
    conexao = get_conexao(); conexao.execute('UPDATE agendamento SET status = ?, observacoes_medicas = ? WHERE protocolo = ? AND ubs_id = ?', (request.form['status'], request.form.get('observacoes', ''), protocolo, session['profissional_ubs_id'])); conexao.commit(); conexao.close(); return redirect(url_for('painel_profissional'))

@app.route('/logout_servidor')
def logout_servidor(): session.pop('profissional_id', None); return redirect(url_for('login_servidor'))

@app.route('/login_gestor', methods=['GET', 'POST'])
def login_gestor():
    e = None
    if request.method == 'POST':
        conexao = get_conexao(); g = conexao.execute('SELECT * FROM gestor WHERE login = ? AND senha = ?', (request.form['login'], request.form['senha'])).fetchone(); conexao.close()
        if g: session['gestor_id']=g['id']; session['gestor_nome']=g['nome']; return redirect(url_for('painel_gestor'))
        else: e = "Dados incorretos."
    return render_template('login_gestor.html', erro=e)

@app.route('/painel_gestor')
def painel_gestor():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    conexao = get_conexao(); t = conexao.execute('SELECT COUNT(*) as q FROM agendamento').fetchone()['q']; f = conexao.execute('SELECT COUNT(*) as q FROM agendamento WHERE status="FINALIZADO"').fetchone()['q']; c = conexao.execute('SELECT COUNT(*) as q FROM agendamento WHERE status="CANCELADO"').fetchone()['q']; r = conexao.execute('''SELECT u.nome as ubs_nome, COUNT(a.protocolo) as total, SUM(CASE WHEN a.status = 'FINALIZADO' THEN 1 ELSE 0 END) as concluidos, SUM(CASE WHEN a.status = 'CANCELADO' THEN 1 ELSE 0 END) as faltas FROM ubs u LEFT JOIN agendamento a ON u.id = a.ubs_id GROUP BY u.id''').fetchall(); conexao.close()
    return render_template('painel_gestor.html', nome=session['gestor_nome'], total=t, finalizados=f, cancelados=c, relatorio_ubs=r)

@app.route('/cadastrar_ubs', methods=['GET', 'POST'])
def cadastrar_ubs():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    m = None; conexao = get_conexao()
    if request.method == 'POST':
        cur = conexao.cursor(); cur.execute('INSERT INTO ubs (nome, endereco) VALUES (?, ?)', (request.form['nome'], request.form['endereco'])); u_id = cur.lastrowid
        for s_id in request.form.getlist('servicos'): cur.execute('INSERT INTO ubs_servico (ubs_id, servico_id) VALUES (?, ?)', (u_id, s_id))
        conexao.commit(); m = f"UBS '{request.form['nome']}' criada!"
    s = conexao.execute('SELECT * FROM servico_saude').fetchall(); conexao.close()
    return render_template('cadastrar_ubs.html', nome=session['gestor_nome'], servicos=s, mensagem=m)

@app.route('/cadastrar_servico', methods=['GET', 'POST'])
def cadastrar_servico():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    m = None
    if request.method == 'POST':
        conexao = get_conexao(); conexao.execute('INSERT INTO servico_saude (nome, descricao, icone) VALUES (?, ?, ?)', (request.form['nome'], request.form['descricao'], request.form['icone'])); conexao.commit(); conexao.close(); m = "Serviço adicionado!"
    return render_template('cadastrar_servico.html', nome=session['gestor_nome'], mensagem=m)

@app.route('/cadastrar_profissional', methods=['GET', 'POST'])
def cadastrar_profissional():
    if 'gestor_id' not in session: return redirect(url_for('login_gestor'))
    m = None; e = None; conexao = get_conexao()
    if request.method == 'POST':
        try: conexao.execute('INSERT INTO profissional (nome, cargo, login, senha, ubs_id) VALUES (?, ?, ?, ?, ?)', (request.form['nome'], request.form['cargo'], request.form['login'], request.form['senha'], request.form['ubs_id'])); conexao.commit(); m = "Profissional cadastrado!"
        except: e = "Login em uso."
    u = conexao.execute('SELECT * FROM ubs ORDER BY nome').fetchall(); conexao.close()
    return render_template('cadastrar_profissional.html', nome=session['gestor_nome'], ubs=u, mensagem=m, erro=e)

@app.route('/logout_gestor')
def logout_gestor(): session.pop('gestor_id', None); return redirect(url_for('login_gestor'))

if __name__ == '__main__':
    app.run(debug=True)