import sqlite3

# Conecta especificamente no banco da nossa pasta
conexao = sqlite3.connect('saude_facil.db')
cursor = conexao.cursor()

try:
    # Inserindo os dados de teste na tabela
    cursor.execute("""
        INSERT INTO usuario (cpf, cartao_sus, nome, senha) 
        VALUES ('12345678900', '123456', 'Gabriel', 'senha123')
    """)
    conexao.commit()
    print("✅ Usuário inserido com sucesso!")
except sqlite3.IntegrityError:
    print("⚠️ O usuário já existe no banco de dados!")
except Exception as e:
    print(f"❌ Erro: {e}")
finally:
    conexao.close()