import streamlit as st
import pandas as pd
import random
import json
import io 

# --- 1. Configurações e Tabela de Prêmios ---
# URL pública do Google Sheets (formato CSV)
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQxxGfjczBE5mAHUPdKniDw7oTfx8udK74bjX_SUCS2sTljsVM_XzRoDb8i2TsHlu1K_uWsI1V8Rk7I/pub?gid=0&single=true&output=csv"

PREMIOS_DO_JOGO = [
    1000, 2000, 3000, 4000, 5000,
    10000, 20000, 30000, 40000, 50000,
    1000000 
]
NUM_PERGUNTAS_TOTAIS = 11
NUM_PERGUNTAS_REGULARES = 10 # 10 perguntas + 1 Milhão

@st.cache_data(ttl=3600)
def load_all_questions():
    """Carrega TODAS as perguntas da planilha uma única vez."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)
        required_cols = ['Pergunta', 'Opção A', 'Opção B', 'Opção C', 'Opção D', 'Resposta Certa']
        
        if not all(col in df.columns for col in required_cols):
             st.error("Erro: A planilha CSV deve conter as colunas necessárias.")
             return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar perguntas da planilha do Google. Verifique a URL e permissões. Erro: {e}")
        return pd.DataFrame()

def initialize_game_state():
    """Inicializa as variáveis de sessão para um novo jogo, garantindo perguntas únicas."""
    
    full_df = load_all_questions()
    if full_df.empty or len(full_df) < NUM_PERGUNTAS_TOTAIS:
        # Se falhar, inicializa com DF vazio para o erro aparecer na tela
        st.session_state['df_perguntas'] = pd.DataFrame()
        return

    # 1. Seleciona 11 perguntas únicas e aleatórias
    perguntas_sorteadas = full_df.sample(n=NUM_PERGUNTAS_TOTAIS).to_dict('records')
    
    # 2. As primeiras 10 são as perguntas regulares
    df_regulares = pd.DataFrame(perguntas_sorteadas[:NUM_PERGUNTAS_REGULARES])
    
    # 3. A última é a Pergunta do Milhão
    pergunta_milhao = perguntas_sorteadas[NUM_PERGUNTAS_REGULARES]

    # Salva no estado
    st.session_state['df_perguntas'] = df_regulares
    st.session_state['pergunta_milhao'] = pergunta_milhao
    
    st.session_state['indice_pergunta'] = 0
    st.session_state['acumulado'] = 0.0
    st.session_state['jogo_encerrado'] = False
    st.session_state['feedback_status'] = 'NENHUM'
    st.session_state['feedback_data'] = None
    
    st.session_state['pulos_restantes'] = 3
    st.session_state['usou_universitarios'] = False
    st.session_state['usou_cartas'] = False
    st.session_state['usou_ia'] = False
    st.session_state['opcoes_eliminadas'] = [] 


# --- Lógica de Prêmios ---
def get_current_prize(index): return PREMIOS_DO_JOGO[index]
def get_stop_prize(index): return st.session_state['acumulado']
def get_error_prize(index): 
    premio_garantido = st.session_state['acumulado']
    if index == 0 or index == NUM_PERGUNTAS_TOTAIS - 1: return 0.0
    return premio_garantido / 2

def _set_feedback_data(current_q, status, selected_option=None):
    st.session_state['feedback_data'] = {
        'pergunta': current_q['Pergunta'],
        'opcoes': {key: current_q[key] for key in ['Opção A', 'Opção B', 'Opção C', 'Opção D']},
        'resposta_certa': current_q['Resposta Certa'],
        'resposta_jogador': selected_option,
        'status': status
    }

def handle_answer(selected_option, current_q):
    if selected_option == current_q['Resposta Certa']:
        st.session_state['acumulado'] = get_current_prize(st.session_state['indice_pergunta'])
        st.session_state['feedback_status'] = 'ACERTO'
        _set_feedback_data(current_q, 'ACERTO', selected_option)
        
        if st.session_state['acumulado'] == 1000000:
            st.session_state['jogo_encerrado'] = True
            st.balloons()
            
    else:
        premio_final = get_error_prize(st.session_state['indice_pergunta'])
        st.session_state['acumulado'] = premio_final
        st.session_state['jogo_encerrado'] = True
        st.session_state['feedback_status'] = 'ERRO'
        _set_feedback_data(current_q, 'ERRO', selected_option)


def handle_stop(current_q):
    st.session_state['jogo_encerrado'] = True
    st.session_state['feedback_status'] = 'PARADA'
    _set_feedback_data(current_q, 'PARADA')


def handle_continue():
    st.session_state['indice_pergunta'] += 1
    st.session_state['feedback_status'] = 'NENHUM'
    st.session_state['feedback_data'] = None
    st.session_state['opcoes_eliminadas'] = []
    st.rerun()

# --- Funções de Ajuda ---

def use_pular():
    if st.session_state['pulos_restantes'] > 0:
        st.session_state['pulos_restantes'] -= 1
        # AVANÇA O ÍNDICE para pegar a próxima pergunta na sequência de prêmios
        st.session_state['indice_pergunta'] += 1 
        st.session_state['opcoes_eliminadas'] = [] 
        st.info("Pergunta pulada! A próxima será carregada.")
        st.rerun() 
    else:
        st.error("Você não tem mais pulos!")

def use_universitarios(current_q):
    if not st.session_state['usou_universitarios']:
        st.session_state['usou_universitarios'] = True
        st.warning("Consultando os Universitários...")
        st.info(f"Os Universitários sugerem a opção: **{current_q['Resposta Certa']}**")
    else:
        st.error("Ajuda 'Universitários' já foi utilizada.")

def use_cartas(current_q):
    if not st.session_state['usou_cartas']:
        st.session_state['usou_cartas'] = True
        
        cartas = {"Ás (1 errada)": 1, "2 (2 erradas)": 2, "3 (3 erradas)": 3, "Rei (0 errada)": 0}
        carta_nome, num_eliminar = random.choice(list(cartas.items()))
        
        st.warning(f"Sorteando Carta: **{carta_nome}**")
        
        opcoes_keys = ['Opção A', 'Opção B', 'Opção C', 'Opção D']
        resposta_certa_key = f"Opção {current_q['Resposta Certa']}"
        
        opcoes_incorretas_keys = [
            key for key in opcoes_keys 
            if key != resposta_certa_key and key not in st.session_state['opcoes_eliminadas']
        ]

        if num_eliminar > 0 and opcoes_incorretas_keys:
            eliminar_keys = random.sample(opcoes_incorretas_keys, min(num_eliminar, len(opcoes_incorretas_keys)))
            st.session_state['opcoes_eliminadas'].extend(eliminar_keys)
            
            eliminar_text = [f"{key}: {current_q[key]}" for key in eliminar_keys]
            st.info(f"Opções Eliminadas: **{', '.join(eliminar_text)}**")
        else:
            st.info("O Rei foi sorteado ou não há opções para eliminar. Boa sorte!")
    else:
        st.error("Ajuda 'Cartas' já foi utilizada.")

def use_ia(current_q):
    if not st.session_state['usou_ia']:
        st.session_state['usou_ia'] = True
        st.warning("Consultando o Assistente Virtual (IA)...")
        st.info(f"O Assistente Virtual indica: **Opção {current_q['Resposta Certa']}**")
    else:
        st.error("Ajuda 'IA' já foi utilizada.")


# --- 3. Telas de Renderização ---

def render_feedback_screen():
    status = st.session_state['feedback_status']
    data = st.session_state['feedback_data']
    acumulado = st.session_state['acumulado']
    
    st.markdown("---")
    
    if status == 'ACERTO':
        st.success(f"✅ **Correto!** Você garantiu R$ {acumulado:,.2f}.")
    elif status == 'ERRO':
        st.error("❌ **Resposta Incorreta!** O jogo terminou.")
    elif status == 'PARADA':
        st.warning("✋ **Você Parou.** O jogo terminou por decisão do jogador.")

    st.subheader("Revisão da Pergunta:")
    st.markdown(f"**{data['pergunta']}**")

    st.markdown("#### Alternativas:")
    for key, text in data['opcoes'].items():
        key_letra = key[-1]
        is_correct = key_letra == data['resposta_certa']
        is_player_answer = key_letra == data['resposta_jogador']
        
        if is_correct:
            st.success(f"**{key_letra}** - {text} **(CORRETA)**", icon="✅")
        elif is_player_answer and status == 'ERRO':
            st.error(f"**{key_letra}** - {text} **(SUA RESPOSTA ERRADA)**", icon="❌")
        else:
            st.markdown(f"**{key_letra}** - {text}")
            
    st.markdown("---")

    if status == 'ACERTO' and acumulado < 1000000:
        st.subheader(f"Próxima Meta: R$ {get_current_prize(st.session_state['indice_pergunta']):,.2f}")
        if st.button("CONTINUAR para a próxima pergunta"):
            handle_continue()
    else:
        st.subheader(f"Prêmio Final: R$ {acumulado:,.2f}")
        st.info("Clique em 'Novo Jogo / Reiniciar' para começar outra partida.")


# --- 4. Função Principal (main) ---

def main():
    st.set_page_config(page_title="Show do Milhão", layout="centered")
    st.title("Show do Milhão")

    if 'indice_pergunta' not in st.session_state:
        initialize_game_state()
    
    if st.session_state['df_perguntas'].empty:
        # Exibe erro se não houver dados suficientes e para o script
        st.error("ERRO CRÍTICO: O jogo não pode iniciar devido à falta de perguntas válidas na planilha.")
        st.stop()


    if st.button("Novo Jogo / Reiniciar"):
        initialize_game_state()
        st.rerun()
        
    # Variáveis de status globais na main
    df = st.session_state['df_perguntas']
    idx = st.session_state['indice_pergunta']
    pergunta_num = idx + 1
    is_pergunta_milhao = (pergunta_num == NUM_PERGUNTAS_TOTAIS)
    premio_acerto = get_current_prize(idx)
    premio_garantido = st.session_state['acumulado']
    premio_parar_texto = f"Parar e Levar R$ {premio_garantido:,.2f}"

    if st.session_state['jogo_encerrado'] and st.session_state['feedback_status'] == 'NENHUM':
        render_feedback_screen()
        return

    # ----------------------------------------------------
    # LÓGICA DE FLUXO E FEEDBACK
    # ----------------------------------------------------
    if st.session_state['feedback_status'] != 'NENHUM':
        render_feedback_screen()
        return 

    # ----------------------------------------------------
    # RENDERIZAÇÃO DA PERGUNTA ATUAL
    # ----------------------------------------------------
    
    if idx >= NUM_PERGUNTAS_REGULARES:
        current_q = st.session_state['pergunta_milhao']
    else:
        current_q = df.iloc[idx].to_dict()
    
    st.markdown("---")
    
    # FORMATO DO TEXTO CORRIGIDO: "Pergunta valendo R$ X.XXX,XX"
    st.subheader(f"Pergunta valendo R$ {premio_acerto:,.2f}")
    
    if is_pergunta_milhao:
        st.error("🚨 PERGUNTA DO MILHÃO! Ajuda indisponível. Se errar, perde tudo.")
        
    st.markdown(f"**{current_q['Pergunta']}**")

    opcoes_keys = ['Opção A', 'Opção B', 'Opção C', 'Opção D']
    opcoes_visiveis_keys = [key for key in opcoes_keys if key not in st.session_state['opcoes_eliminadas']]
    opcoes_display = [f"{key}: {current_q[key]}" for key in opcoes_visiveis_keys]
    
    with st.form(key='answer_form'):
        selected_display = st.radio("Selecione sua resposta:", options=opcoes_display, index=None, key='radio_opcoes')
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Responder"):
                if selected_display is None:
                    st.warning("Por favor, selecione uma opção.")
                else:
                    selected_option = selected_display.split(":")[0][-1]
                    handle_answer(selected_option, current_q)
                    st.rerun() 
        
        if pergunta_num > 1:
            with col2:
                # O botão Parar mostra o valor GARANTIDO (R$ 0.00 se nunca acertou)
                if st.form_submit_button(premio_parar_texto):
                    handle_stop(current_q)
                    st.rerun() 


    # -------------------
    # D. Sidebar e Recursos
    # -------------------
    
    st.sidebar.markdown(f"**Prêmio da Pergunta:** R$ {premio_acerto:,.2f}")
    st.sidebar.markdown(f"**Prêmio Acumulado:** R$ {premio_garantido:,.2f}")

    if pergunta_num > 1:
        st.sidebar.markdown(f"**Se Parar, Leva:** R$ {premio_garantido:,.2f}")
    
    if not is_pergunta_milhao:
        if pergunta_num == 1:
            premio_a_perder = 0.0
        else:
            premio_a_perder = premio_garantido / 2
        st.sidebar.markdown(f"**Se Errar, Leva:** R$ {premio_a_perder:,.2f}")
    else:
        st.sidebar.markdown(f"**Se Errar, Leva:** R$ 0,00")


    st.sidebar.header("Recursos (Ajudas)")
    disabled_aids = is_pergunta_milhao

    col_pulo, col_uni = st.sidebar.columns(2)
    col_carta, col_ia = st.sidebar.columns(2)
    
    if st.session_state['pulos_restantes'] > 0 and not disabled_aids:
        if col_pulo.button(f"Pular ({st.session_state['pulos_restantes']})"):
            use_pular()
    else:
        col_pulo.button(f"Pular ({st.session_state['pulos_restantes']})", disabled=True)
        
    if not st.session_state['usou_universitarios'] and not disabled_aids:
        if col_uni.button("Universitários"):
            use_universitarios(current_q)
    else:
        col_uni.button("Universitários (Usado)", disabled=True)

    if not st.session_state['usou_cartas'] and not disabled_aids:
        if col_carta.button("Cartas"):
            use_cartas(current_q)
    else:
        col_carta.button("Cartas (Usado)", disabled=True)

    if not st.session_state['usou_ia'] and not disabled_aids:
        if col_ia.button("Assistente Virtual (IA)"):
            use_ia(current_q)
    else:
        col_ia.button("Assistente Virtual (Usado)", disabled=True)


if __name__ == "__main__":

    main()
