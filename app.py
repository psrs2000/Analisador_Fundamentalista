"""
app.py
Analisador Fundamentalista — Interface Streamlit
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import time

from data_fetcher import fetch_all_companies, fetch_company_data
from scorer import calcular_todos_scores
from cache_manager import (
    verificar_cache, carregar_do_cache, salvar_no_cache,
    limpar_cache, info_cache
)

# ====================================================================
# CONFIGURAÇÃO DA PÁGINA
# ====================================================================
st.set_page_config(
    page_title="Analisador Fundamentalista",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1f4e79;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .score-card {
        background: linear-gradient(135deg, #1f4e79, #2e75b6);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 0.8rem;
        border-radius: 8px;
        border-left: 4px solid #2e75b6;
        margin-bottom: 0.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)


# ====================================================================
# FUNÇÕES AUXILIARES
# ====================================================================

def formatar_valor(val, tipo="numero"):
    """Formata valores para exibição."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/D"
    if tipo == "pct":
        return f"{val*100:.1f}%"
    if tipo == "moeda":
        if abs(val) >= 1e9:
            return f"R$ {val/1e9:.1f}B"
        if abs(val) >= 1e6:
            return f"R$ {val/1e6:.1f}M"
        return f"R$ {val:,.0f}"
    if tipo == "multiplo":
        return f"{val:.1f}x"
    if tipo == "score":
        return f"{val:.1f}"
    return f"{val:,.2f}"


def cor_score(score):
    """Retorna cor baseada no score."""
    if score is None:
        return "#999"
    if score >= 7.5:
        return "#28a745"
    if score >= 5.0:
        return "#ffc107"
    if score >= 2.5:
        return "#fd7e14"
    return "#dc3545"


def badge_score(score, label=""):
    """HTML badge colorido para score."""
    if score is None:
        return f'<span style="background:#eee;padding:3px 8px;border-radius:12px;font-size:0.85rem">N/D</span>'
    cor = cor_score(score)
    return f'<span style="background:{cor};color:white;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:0.9rem">{score:.1f}</span>'


def gauge_chart(score, title):
    """Cria gráfico gauge para score."""
    if score is None:
        score = 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 10], "tickwidth": 1},
            "bar": {"color": cor_score(score)},
            "steps": [
                {"range": [0, 2.5], "color": "#ffe0e0"},
                {"range": [2.5, 5.0], "color": "#fff3cd"},
                {"range": [5.0, 7.5], "color": "#d4edda"},
                {"range": [7.5, 10], "color": "#c3e6cb"},
            ],
            "threshold": {
                "line": {"color": "black", "width": 2},
                "thickness": 0.75,
                "value": score
            }
        }
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def df_para_excel(df: pd.DataFrame) -> BytesIO:
    """Converte DataFrame para Excel em memória."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ranking")
    output.seek(0)
    return output


# ====================================================================
# SIDEBAR — CONFIGURAÇÕES
# ====================================================================

def render_sidebar():
    """Renderiza a sidebar com todas as configurações."""
    st.sidebar.markdown("## ⚙️ Configurações")

    # --- Pesos Qualidade ---
    st.sidebar.markdown("### 🏆 Pesos — Qualidade")
    st.sidebar.caption("Os pesos devem somar 100%")

    w_rent = st.sidebar.slider("Rentabilidade", 0, 100, 15, 5, key="w_rent")
    w_div  = st.sidebar.slider("Capacidade de Dívida", 0, 100, 25, 5, key="w_div")
    w_cx   = st.sidebar.slider("Geração de Caixa", 0, 100, 25, 5, key="w_cx")
    w_cres = st.sidebar.slider("Crescimento", 0, 100, 15, 5, key="w_cres")
    w_efi  = st.sidebar.slider("Eficiência Operacional", 0, 100, 20, 5, key="w_efi")

    soma_q = w_rent + w_div + w_cx + w_cres + w_efi
    if soma_q != 100:
        st.sidebar.warning(f"⚠️ Soma atual: {soma_q}% (deve ser 100%)")
    else:
        st.sidebar.success(f"✅ Soma: {soma_q}%")

    # --- Pesos Valuation ---
    st.sidebar.markdown("### 💰 Pesos — Valuation")

    w_abs  = st.sidebar.slider("Valuation Absoluto", 0, 100, 35, 5, key="w_abs")
    w_hist = st.sidebar.slider("Múltiplos vs. Histórico", 0, 100, 35, 5, key="w_hist")
    w_set  = st.sidebar.slider("Múltiplos vs. Setor", 0, 100, 30, 5, key="w_set")

    soma_v = w_abs + w_hist + w_set
    if soma_v != 100:
        st.sidebar.warning(f"⚠️ Soma atual: {soma_v}% (deve ser 100%)")
    else:
        st.sidebar.success(f"✅ Soma: {soma_v}%")

    # --- Score Final ---
    st.sidebar.markdown("### 🎯 Score Final")
    peso_q_final = st.sidebar.slider("Peso Qualidade no Score Final", 0, 100, 50, 5, key="w_q_final")
    peso_v_final = 100 - peso_q_final
    st.sidebar.info(f"Qualidade: {peso_q_final}% | Valuation: {peso_v_final}%")

    # --- Método Preço Justo ---
    st.sidebar.markdown("### 📐 Método — Preço Justo")
    metodo_pj = st.sidebar.radio(
        "Calcular preço justo por:",
        ["Média (Graham + DCF)", "Graham", "DCF"],
        key="metodo_pj"
    )
    metodo_map = {"Média (Graham + DCF)": "media", "Graham": "graham", "DCF": "dcf"}

    return {
        "pesos_qualidade": {
            "rentabilidade": w_rent / 100,
            "divida": w_div / 100,
            "caixa": w_cx / 100,
            "crescimento": w_cres / 100,
            "eficiencia": w_efi / 100,
        },
        "pesos_valuation": {
            "absoluto": w_abs / 100,
            "historico": w_hist / 100,
            "setor": w_set / 100,
        },
        "peso_q_final": peso_q_final / 100,
        "peso_v_final": peso_v_final / 100,
        "metodo_pj": metodo_map[metodo_pj],
        "soma_q_ok": soma_q == 100,
        "soma_v_ok": soma_v == 100,
    }


# ====================================================================
# TELA 1 — UPLOAD E ANÁLISE
# ====================================================================

def tela_upload(config):
    """Tela principal de upload e disparo da análise."""
    st.markdown('<p class="main-header">📊 Analisador Fundamentalista</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ranking inteligente de empresas por Qualidade e Valuation</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📁 Carregar Lista de Empresas")
        st.markdown("""
        Faça upload de um arquivo **CSV ou XLSX** com as colunas:
        - `ticker` — código da ação (ex: VALE3.SA, PETR4.SA, AAPL)
        - `nome` — nome amigável da empresa
        - `setor` — setor para comparação entre pares
        """)

        arquivo = st.file_uploader(
            "Selecione o arquivo",
            type=["csv", "xlsx"],
        )

        # Exemplo para download
        df_exemplo = pd.DataFrame({
            "ticker": ["VALE3.SA", "PETR4.SA", "ITUB4.SA", "WEGE3.SA", "BBDC4.SA"],
            "nome":   ["Vale", "Petrobras", "Itaú Unibanco", "WEG", "Bradesco"],
            "setor":  ["Mineração", "Petróleo e Gás", "Bancos", "Indústria", "Bancos"]
        })

        st.download_button(
            "📥 Baixar arquivo de exemplo",
            df_exemplo.to_csv(index=False).encode("utf-8"),
            "empresas_exemplo.csv",
            "text/csv"
        )

    with col2:
        st.markdown("### 📋 Formato esperado")
        st.dataframe(df_exemplo, hide_index=True, use_container_width=True)

    # Processar arquivo
    if arquivo is not None:
        try:
            if arquivo.name.endswith(".csv"):
                df = pd.read_csv(arquivo)
            else:
                df = pd.read_excel(arquivo)

            # Validar colunas
            colunas_req = {"ticker", "nome", "setor"}
            if not colunas_req.issubset(set(df.columns.str.lower())):
                st.error("❌ O arquivo deve ter as colunas: ticker, nome, setor")
                return

            df.columns = df.columns.str.lower()
            df = df[["ticker", "nome", "setor"]].dropna(subset=["ticker"])

            st.success(f"✅ {len(df)} empresas carregadas")
            st.dataframe(df, hide_index=True, use_container_width=True)

            # Validar pesos
            if not config["soma_q_ok"]:
                st.error("❌ Os pesos de Qualidade na sidebar devem somar 100% antes de analisar.")
                return
            if not config["soma_v_ok"]:
                st.error("❌ Os pesos de Valuation na sidebar devem somar 100% antes de analisar.")
                return

            empresas = df.to_dict("records")

            # --- Status do cache ---
            st.markdown("### 🗄️ Cache de Dados")
            estado_cache = verificar_cache(empresas)
            info = info_cache()

            if estado_cache["status"] == "completo":
                st.success(
                    f"✅ Cache válido para todas as {len(empresas)} empresas  "
                    f"— dados de {estado_cache['data_mais_antiga']}"
                )
            elif estado_cache["status"] == "parcial":
                st.info(
                    f"⚡ Cache parcial: {len(estado_cache['tickers_ok'])} empresas em cache, "
                    f"{len(estado_cache['tickers_faltando'])} precisam ser buscadas."
                )
            else:
                st.warning("📭 Nenhum cache disponível — será necessário buscar todos os dados.")

            if info:
                with st.expander("ℹ️ Detalhes do cache"):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Tickers em cache", info["total_tickers"])
                    col_b.metric("Última atualização", info["atualizado_em"] or "—")
                    col_c.metric("Tamanho do arquivo", f"{info['tamanho_kb']} KB")

            # --- Botões de ação ---
            col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])

            with col_btn1:
                label_btn = (
                    "⚡ Calcular Scores (usando cache)"
                    if estado_cache["status"] == "completo"
                    else "🚀 Iniciar Análise"
                )
                iniciar = st.button(label_btn, type="primary", use_container_width=True)

            with col_btn2:
                forcar = st.button(
                    "🔄 Forçar Atualização",
                    use_container_width=True,
                    help="Ignora o cache e busca dados frescos do Yahoo Finance"
                )

            with col_btn3:
                if st.button("🗑️ Limpar Cache", use_container_width=True):
                    limpar_cache()
                    st.success("Cache limpo!")
                    st.rerun()

            # --- Recalcular scores se já tiver dados em cache e parâmetros mudaram ---
            dados_em_cache = st.session_state.get("dados_brutos")
            config_anterior = st.session_state.get("config_anterior")
            parametros_mudaram = config_anterior != {
                k: v for k, v in config.items()
                if k in ["pesos_qualidade", "pesos_valuation", "peso_q_final",
                         "peso_v_final", "metodo_pj"]
            }

            if dados_em_cache and parametros_mudaram and not iniciar and not forcar:
                st.info("🔁 Parâmetros alterados — recalculando scores automaticamente...")
                _recalcular_scores(dados_em_cache, config)

            if iniciar:
                _executar_analise(empresas, config, forcar_atualizacao=False)

            if forcar:
                _executar_analise(empresas, config, forcar_atualizacao=True)

        except Exception as e:
            st.error(f"❌ Erro ao ler arquivo: {e}")


def _recalcular_scores(dados_brutos: dict, config: dict):
    """Recalcula apenas os scores sem buscar dados novos — instantâneo."""
    resultados = calcular_todos_scores(
        dados_empresas=dados_brutos,
        pesos_qualidade=config["pesos_qualidade"],
        pesos_valuation=config["pesos_valuation"],
        peso_q_final=config["peso_q_final"],
        peso_v_final=config["peso_v_final"],
        metodo_pj=config["metodo_pj"],
    )
    st.session_state["resultados"] = resultados
    st.session_state["analise_ok"] = True
    st.session_state["config_anterior"] = {
        k: v for k, v in config.items()
        if k in ["pesos_qualidade", "pesos_valuation", "peso_q_final",
                 "peso_v_final", "metodo_pj"]
    }
    st.rerun()


def _executar_analise(empresas, config, forcar_atualizacao: bool = False):
    """
    Executa a análise completa com suporte a cache.
    - forcar_atualizacao=False: usa cache quando disponível
    - forcar_atualizacao=True: ignora cache e busca tudo do Yahoo
    """
    from cache_manager import verificar_cache, carregar_do_cache, salvar_no_cache

    progress = st.progress(0, text="Iniciando análise...")
    status = st.empty()
    dados = {}

    if forcar_atualizacao:
        # Limpar cache e buscar tudo
        limpar_cache()
        tickers_buscar = [e["ticker"] for e in empresas]
        cache_disponivel = {}
    else:
        # Verificar o que já está em cache
        estado = verificar_cache(empresas)
        tickers_buscar = estado["tickers_faltando"]
        # Carregar do cache os que já existem
        cache_disponivel = carregar_do_cache(estado["tickers_ok"])

    total_buscar = len(tickers_buscar)
    total_cache = len(cache_disponivel)

    if total_cache > 0 and not forcar_atualizacao:
        status.text(f"📦 {total_cache} empresa(s) carregadas do cache...")

    # Buscar apenas os que faltam
    empresas_map = {e["ticker"].upper().strip(): e for e in empresas}

    for i, ticker in enumerate(tickers_buscar):
        emp = empresas_map.get(ticker.upper().strip(), {"ticker": ticker, "nome": ticker, "setor": ""})
        status.text(f"🔍 Buscando {emp.get('nome', ticker)} ({ticker})... [{i+1}/{total_buscar}]")
        progress.progress(
            i / max(total_buscar, 1),
            text=f"Buscando dados do Yahoo Finance: {ticker}..."
        )

        data = fetch_company_data(ticker)
        data["nome_usuario"] = emp.get("nome", ticker)
        data["setor_usuario"] = emp.get("setor", "")
        dados[ticker.upper().strip()] = data
        time.sleep(0.3)

    # Salvar novos dados no cache
    if dados:
        from cache_manager import verificar_cache as _vc
        chave = _vc(empresas)["chave_atual"]
        salvar_no_cache(dados, chave)

    # Combinar cache + novos dados
    for ticker, data_cache in cache_disponivel.items():
        if ticker not in dados:
            emp = empresas_map.get(ticker, {"ticker": ticker, "nome": ticker, "setor": ""})
            dados[ticker] = data_cache
            dados[ticker]["nome_usuario"] = emp.get("nome", ticker)
            dados[ticker]["setor_usuario"] = emp.get("setor", "")

    progress.progress(1.0, text="Calculando scores...")
    status.text("🧮 Calculando scores...")

    resultados = calcular_todos_scores(
        dados_empresas=dados,
        pesos_qualidade=config["pesos_qualidade"],
        pesos_valuation=config["pesos_valuation"],
        peso_q_final=config["peso_q_final"],
        peso_v_final=config["peso_v_final"],
        metodo_pj=config["metodo_pj"],
    )

    # Salvar dados brutos e resultados no session_state
    st.session_state["dados_brutos"] = dados
    st.session_state["resultados"] = resultados
    st.session_state["config"] = config
    st.session_state["analise_ok"] = True
    st.session_state["config_anterior"] = {
        k: v for k, v in config.items()
        if k in ["pesos_qualidade", "pesos_valuation", "peso_q_final",
                 "peso_v_final", "metodo_pj"]
    }

    progress.empty()
    status.empty()

    ok = sum(1 for r in resultados.values() if r.get("score_final") is not None)
    origem = "Yahoo Finance" if forcar_atualizacao or not cache_disponivel else f"cache ({total_cache}) + Yahoo ({total_buscar})"
    st.success(f"✅ {ok} empresas analisadas com sucesso  —  Fonte: {origem}")
    st.rerun()


# ====================================================================
# TELA 2 — RANKING
# ====================================================================

def tela_ranking():
    """Exibe o ranking completo das empresas."""
    resultados = st.session_state.get("resultados", {})
    if not resultados:
        st.info("Carregue um arquivo e execute a análise primeiro.")
        return

    st.markdown("## 🏆 Ranking de Empresas")

    # Montar DataFrame do ranking
    rows = []
    for ticker, r in resultados.items():
        if r.get("score_final") is None:
            rows.append({
                "Ticker": ticker,
                "Empresa": r.get("nome", ticker),
                "Setor": r.get("setor", ""),
                "Score Final": None,
                "Qualidade": None,
                "Valuation": None,
                "Preço": None,
                "P/L": None,
                "P/VP": None,
                "EV/EBITDA": None,
                "ROE": None,
                "Margem Líq.": None,
                "Div. Yield": None,
                "Upside": None,
                "Status": f"❌ {r.get('erro', 'Erro')}",
            })
        else:
            rows.append({
                "Ticker": ticker,
                "Empresa": r.get("nome", ticker),
                "Setor": r.get("setor", ""),
                "Score Final": r.get("score_final"),
                "Qualidade": r.get("score_qualidade"),
                "Valuation": r.get("score_valuation"),
                "Preço": r.get("preco_atual"),
                "P/L": r.get("pl"),
                "P/VP": r.get("pvp"),
                "EV/EBITDA": r.get("ev_ebitda"),
                "ROE": r.get("roe"),
                "Margem Líq.": r.get("margem_liquida"),
                "Div. Yield": r.get("dividend_yield"),
                "Upside": r.get("upside"),
                "Status": "✅",
            })

    df = pd.DataFrame(rows)
    df_ok = df[df["Score Final"].notna()].sort_values("Score Final", ascending=False).reset_index(drop=True)
    df_ok.index += 1  # ranking começa em 1

    # Filtros
    col1, col2 = st.columns([2, 1])
    with col1:
        setores = ["Todos"] + sorted(df_ok["Setor"].unique().tolist())
        setor_filtro = st.selectbox("Filtrar por setor:", setores)
    with col2:
        ordenar = st.selectbox("Ordenar por:", ["Score Final", "Qualidade", "Valuation", "Upside"])

    if setor_filtro != "Todos":
        df_ok = df_ok[df_ok["Setor"] == setor_filtro]

    df_ok = df_ok.sort_values(ordenar, ascending=False).reset_index(drop=True)
    df_ok.index += 1

    # Formatar para exibição — converte para float primeiro para evitar erro com strings do cache
    def fmt(val, fmt_str, multiplier=1, prefix="", suffix=""):
        try:
            v = float(val) * multiplier
            return f"{prefix}{v:{fmt_str}}{suffix}"
        except (TypeError, ValueError):
            return "N/D"

    df_display = df_ok.copy()
    df_display["Score Final"] = df_display["Score Final"].apply(lambda x: fmt(x, ".2f"))
    df_display["Qualidade"]   = df_display["Qualidade"].apply(lambda x: fmt(x, ".2f"))
    df_display["Valuation"]   = df_display["Valuation"].apply(lambda x: fmt(x, ".2f"))
    df_display["Preço"]       = df_display["Preço"].apply(lambda x: fmt(x, ".2f", prefix="R$ "))
    df_display["P/L"]         = df_display["P/L"].apply(lambda x: fmt(x, ".1f", suffix="x"))
    df_display["P/VP"]        = df_display["P/VP"].apply(lambda x: fmt(x, ".1f", suffix="x"))
    df_display["EV/EBITDA"]   = df_display["EV/EBITDA"].apply(lambda x: fmt(x, ".1f", suffix="x"))
    df_display["ROE"]         = df_display["ROE"].apply(lambda x: fmt(x, ".1f", multiplier=100, suffix="%"))
    df_display["Margem Líq."] = df_display["Margem Líq."].apply(lambda x: fmt(x, ".1f", multiplier=100, suffix="%"))
    df_display["Div. Yield"]  = df_display["Div. Yield"].apply(lambda x: fmt(x, ".1f", multiplier=100, suffix="%"))
    df_display["Upside"]      = df_display["Upside"].apply(lambda x: fmt(x, ".1f", multiplier=100, suffix="%"))

    st.dataframe(
        df_display[["Empresa", "Setor", "Score Final", "Qualidade", "Valuation",
                    "Preço", "Upside", "P/L", "P/VP", "ROE", "Div. Yield"]],
        use_container_width=True,
        height=500
    )

    # Erros
    df_err = df[df["Score Final"].isna()]
    if not df_err.empty:
        with st.expander(f"⚠️ {len(df_err)} empresa(s) com erro"):
            st.dataframe(df_err[["Ticker", "Empresa", "Status"]], hide_index=True)

    # Gráfico de dispersão Qualidade x Valuation
    st.markdown("### 🎯 Mapa Qualidade × Valuation")
    st.caption("Ideal: canto superior direito (alta qualidade + bom valuation)")

    fig = px.scatter(
        df_ok,
        x="Valuation", y="Qualidade",
        text="Ticker",
        size_max=20,
        color="Score Final",
        color_continuous_scale="RdYlGn",
        range_color=[0, 10],
        labels={"Valuation": "Score Valuation", "Qualidade": "Score Qualidade"},
        hover_data={"Empresa": True, "Setor": True, "Score Final": ":.2f"},
    )
    fig.update_traces(textposition="top center", marker=dict(size=14))
    fig.add_hline(y=5, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=5, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_annotation(x=8.5, y=8.5, text="⭐ Ideal", showarrow=False, font=dict(color="green", size=13))
    fig.add_annotation(x=2,   y=2,   text="🔴 Evitar", showarrow=False, font=dict(color="red", size=13))
    fig.add_annotation(x=2,   y=8.5, text="💎 Cara mas boa", showarrow=False, font=dict(color="orange", size=13))
    fig.add_annotation(x=7,   y=2,   text="🔍 Especulação", showarrow=False, font=dict(color="orange", size=13))
    fig.update_layout(height=500, xaxis=dict(range=[0, 10]), yaxis=dict(range=[0, 10]))
    st.plotly_chart(fig, use_container_width=True)

    # Exportar
    st.markdown("### 📤 Exportar Resultados")
    col1, col2 = st.columns(2)
    with col1:
        excel_data = df_para_excel(df_ok.drop(columns=["Status"], errors="ignore"))
        st.download_button(
            "📥 Baixar Excel",
            excel_data,
            "ranking_fundamentalista.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col2:
        csv_data = df_ok.drop(columns=["Status"], errors="ignore").to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Baixar CSV",
            csv_data,
            "ranking_fundamentalista.csv",
            "text/csv",
            use_container_width=True
        )


# ====================================================================
# TELA 3 — DETALHE DA EMPRESA
# ====================================================================

def tela_detalhe():
    """Tela de detalhe completo de uma empresa."""
    resultados = st.session_state.get("resultados", {})
    if not resultados:
        st.info("Execute a análise primeiro.")
        return

    st.markdown("## 🔍 Detalhe da Empresa")

    # Seletor de empresa
    empresas_ok = {t: r for t, r in resultados.items() if r.get("score_final") is not None}
    if not empresas_ok:
        st.warning("Nenhuma empresa com dados disponíveis.")
        return

    opcoes = {f"{r['nome']} ({t})": t for t, r in empresas_ok.items()}
    escolha = st.selectbox("Selecionar empresa:", list(opcoes.keys()))
    ticker = opcoes[escolha]
    r = resultados[ticker]
    ind = r.get("indicadores_completos", {})

    # Cabeçalho
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Empresa", r["nome"])
    with col2:
        st.metric("Setor", r["setor"])
    with col3:
        preco = r.get("preco_atual")
        st.metric("Preço Atual", f"R$ {preco:.2f}" if preco else "N/D")
    with col4:
        upside = r.get("upside")
        pj = r.get("preco_justo")
        st.metric("Preço Justo Est.", f"R$ {pj:.2f}" if pj else "N/D",
                  delta=f"{upside*100:.1f}%" if upside else None)

    st.divider()

    # Gauges de score
    col1, col2, col3 = st.columns(3)
    with col1:
        st.plotly_chart(gauge_chart(r.get("score_final"), "Score Final"), use_container_width=True)
    with col2:
        st.plotly_chart(gauge_chart(r.get("score_qualidade"), "Qualidade"), use_container_width=True)
    with col3:
        st.plotly_chart(gauge_chart(r.get("score_valuation"), "Valuation"), use_container_width=True)

    st.divider()

    # Sub-scores detalhados
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏆 Qualidade — Sub-scores")
        dq = r.get("detalhes_qualidade", {})
        nomes = {
            "rentabilidade": "Rentabilidade",
            "divida": "Capacidade de Dívida",
            "caixa": "Geração de Caixa",
            "crescimento": "Crescimento",
            "eficiencia": "Eficiência Operacional"
        }
        sub_data = []
        for key, nome in nomes.items():
            s = dq.get(key, {}).get("score")
            sub_data.append({"Critério": nome, "Score": s if s else 0})

        df_sub = pd.DataFrame(sub_data)
        fig_bar = px.bar(df_sub, x="Score", y="Critério", orientation="h",
                         color="Score", color_continuous_scale="RdYlGn",
                         range_color=[0, 10], range_x=[0, 10])
        fig_bar.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0),
                               coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

        # Detalhes das métricas
        for key, nome in nomes.items():
            det = dq.get(key, {}).get("detalhes", {})
            score = dq.get(key, {}).get("score")
            if det:
                with st.expander(f"{nome} — {score:.1f}/10" if score else nome):
                    for k, v in det.items():
                        st.markdown(f"- **{k}:** {v}")

    with col2:
        st.markdown("#### 💰 Valuation — Sub-scores")
        dv = r.get("detalhes_valuation", {})
        nomes_v = {
            "absoluto": "Valuation Absoluto",
            "historico": "Múltiplos vs. Histórico",
            "setor": "Múltiplos vs. Setor"
        }
        sub_data_v = []
        for key, nome in nomes_v.items():
            s = dv.get(key, {}).get("score")
            sub_data_v.append({"Critério": nome, "Score": s if s else 0})

        df_sub_v = pd.DataFrame(sub_data_v)
        fig_bar_v = px.bar(df_sub_v, x="Score", y="Critério", orientation="h",
                           color="Score", color_continuous_scale="RdYlGn",
                           range_color=[0, 10], range_x=[0, 10])
        fig_bar_v.update_layout(height=200, margin=dict(l=0, r=0, t=20, b=0),
                                 coloraxis_showscale=False)
        st.plotly_chart(fig_bar_v, use_container_width=True)

        for key, nome in nomes_v.items():
            det = dv.get(key, {}).get("detalhes", {})
            score = dv.get(key, {}).get("score")
            if det:
                with st.expander(f"{nome} — {score:.1f}/10" if score else nome):
                    for k, v in det.items():
                        st.markdown(f"- **{k}:** {v}")

    st.divider()

    # Indicadores fundamentais
    st.markdown("#### 📈 Indicadores Fundamentais")
    col1, col2, col3, col4 = st.columns(4)

    metricas = [
        ("P/L", ind.get("pl"), "multiplo"),
        ("P/VP", ind.get("pvp"), "multiplo"),
        ("EV/EBITDA", ind.get("ev_ebitda"), "multiplo"),
        ("ROE", ind.get("roe"), "pct"),
        ("ROA", ind.get("roa"), "pct"),
        ("Margem Bruta", ind.get("margem_bruta"), "pct"),
        ("Margem EBIT", ind.get("margem_ebit"), "pct"),
        ("Margem Líquida", ind.get("margem_liquida"), "pct"),
        ("Dividend Yield", ind.get("dividend_yield"), "pct"),
        ("Dívida/PL", ind.get("divida_pl"), "numero"),
        ("Beta", ind.get("beta"), "numero"),
        ("FCF Yield", ind.get("fcf_yield"), "pct"),
    ]

    cols = [col1, col2, col3, col4]
    for i, (nome, val, tipo) in enumerate(metricas):
        with cols[i % 4]:
            st.metric(nome, formatar_valor(val, tipo))

    # Gráficos históricos
    st.divider()
    st.markdown("#### 📊 Evolução Histórica")

    tab1, tab2, tab3 = st.tabs(["📈 DRE", "🏦 Balanço", "💵 Caixa"])

    with tab1:
        _grafico_historico(ind, "receitas_hist", "lucros_hist", "ebitda_hist",
                           ["Receita", "Lucro Líquido", "EBITDA"], chart_key="dre")
    with tab2:
        _grafico_historico(ind, "equity_hist", "total_debt_hist", "net_debt_hist",
                           ["Patrimônio Líquido", "Dívida Total", "Dívida Líquida"], chart_key="balanco")
    with tab3:
        _grafico_historico(ind, "op_cf_hist", "fcf_hist", "capex_hist",
                           ["Fluxo Operacional", "FCF", "Capex"], chart_key="caixa")


def _grafico_historico(ind, *keys_e_labels, chart_key: str = ""):
    """Plota gráfico de barras para séries históricas."""
    keys = keys_e_labels[:-1]
    labels = keys_e_labels[-1]
    n_anos = 4

    anos_labels = [f"Ano -{i}" for i in range(n_anos)]
    anos_labels[0] = "Mais recente"

    fig = go.Figure()
    cores = ["#2e75b6", "#28a745", "#dc3545", "#ffc107"]

    for i, (key, label) in enumerate(zip(keys, labels)):
        vals = ind.get(key, [])[:n_anos]
        if vals:
            # Preencher com None se tiver menos de n_anos
            while len(vals) < n_anos:
                vals.append(None)
            fig.add_trace(go.Bar(
                name=label,
                x=anos_labels,
                y=[v/1e9 if v else None for v in vals],
                marker_color=cores[i % len(cores)]
            ))

    fig.update_layout(
        barmode="group",
        yaxis_title="Bilhões (R$)",
        height=350,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, use_container_width=True, key=f"hist_{chart_key}")


# ====================================================================
# TELA 4 — COMPARAÇÃO
# ====================================================================

def tela_comparacao():
    """Comparação lado a lado entre empresas selecionadas."""
    resultados = st.session_state.get("resultados", {})
    if not resultados:
        st.info("Execute a análise primeiro.")
        return

    st.markdown("## ⚖️ Comparação entre Empresas")

    empresas_ok = {t: r for t, r in resultados.items() if r.get("score_final") is not None}
    opcoes = {f"{r['nome']} ({t})": t for t, r in empresas_ok.items()}

    selecionadas = st.multiselect(
        "Selecionar empresas para comparar (2-6):",
        list(opcoes.keys()),
        max_selections=6
    )

    if len(selecionadas) < 2:
        st.info("Selecione pelo menos 2 empresas para comparar.")
        return

    tickers_sel = [opcoes[s] for s in selecionadas]
    dados_sel = {t: resultados[t] for t in tickers_sel}

    # Tabela comparativa de scores
    st.markdown("### 🏆 Scores Comparativos")
    comp_data = []
    for t, r in dados_sel.items():
        ind = r.get("indicadores_completos", {})
        comp_data.append({
            "Empresa": r["nome"],
            "Score Final": r.get("score_final"),
            "Qualidade": r.get("score_qualidade"),
            "Valuation": r.get("score_valuation"),
            "Preço": r.get("preco_atual"),
            "Preço Justo": r.get("preco_justo"),
            "Upside": r.get("upside"),
            "P/L": ind.get("pl"),
            "P/VP": ind.get("pvp"),
            "EV/EBITDA": ind.get("ev_ebitda"),
            "ROE": ind.get("roe"),
            "Margem Líq.": ind.get("margem_liquida"),
            "Div. Yield": ind.get("dividend_yield"),
            "CAGR Receita": ind.get("cagr_receita"),
            "CAGR Lucro": ind.get("cagr_lucro"),
        })

    df_comp = pd.DataFrame(comp_data).set_index("Empresa")

    # Radar chart de scores
    st.markdown("### 🕸️ Radar de Qualidade")
    config_sess = st.session_state.get("config", {})
    dq_keys = ["rentabilidade", "divida", "caixa", "crescimento", "eficiencia"]
    dq_labels = ["Rentabilidade", "Dívida", "Caixa", "Crescimento", "Eficiência"]

    fig_radar = go.Figure()
    cores_radar = px.colors.qualitative.Set1

    for i, (t, r) in enumerate(dados_sel.items()):
        dq = r.get("detalhes_qualidade", {})
        valores = [dq.get(k, {}).get("score", 5) for k in dq_keys]
        valores_fechado = valores + [valores[0]]  # fechar o polígono
        labels_fechado = dq_labels + [dq_labels[0]]

        fig_radar.add_trace(go.Scatterpolar(
            r=valores_fechado,
            theta=labels_fechado,
            fill="toself",
            name=r["nome"],
            opacity=0.6,
            line_color=cores_radar[i % len(cores_radar)]
        ))

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        height=450,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Tabela formatada
    st.markdown("### 📋 Indicadores Lado a Lado")

    def fmt_safe(val, fmt_str, multiplier=1, prefix="", suffix=""):
        try:
            v = float(val) * multiplier
            return f"{prefix}{v:{fmt_str}}{suffix}"
        except (TypeError, ValueError):
            return "N/D"

    df_fmt = df_comp.copy()
    for col in ["Score Final", "Qualidade", "Valuation"]:
        df_fmt[col] = df_fmt[col].apply(lambda x: fmt_safe(x, ".2f"))
    for col in ["Preço", "Preço Justo"]:
        df_fmt[col] = df_fmt[col].apply(lambda x: fmt_safe(x, ".2f", prefix="R$ "))
    for col in ["Upside", "ROE", "Margem Líq.", "Div. Yield", "CAGR Receita", "CAGR Lucro"]:
        df_fmt[col] = df_fmt[col].apply(lambda x: fmt_safe(x, ".1f", multiplier=100, suffix="%"))
    for col in ["P/L", "P/VP", "EV/EBITDA"]:
        df_fmt[col] = df_fmt[col].apply(lambda x: fmt_safe(x, ".1f", suffix="x"))

    st.dataframe(df_fmt.T, use_container_width=True)

    # Gráfico de barras comparativo dos scores
    st.markdown("### 📊 Scores Comparativos")
    fig_comp = go.Figure()
    nomes = [resultados[t]["nome"] for t in tickers_sel]
    scores_finais = [resultados[t].get("score_final", 0) for t in tickers_sel]
    scores_q = [resultados[t].get("score_qualidade", 0) for t in tickers_sel]
    scores_v = [resultados[t].get("score_valuation", 0) for t in tickers_sel]

    fig_comp.add_trace(go.Bar(name="Score Final", x=nomes, y=scores_finais, marker_color="#1f4e79"))
    fig_comp.add_trace(go.Bar(name="Qualidade", x=nomes, y=scores_q, marker_color="#28a745"))
    fig_comp.add_trace(go.Bar(name="Valuation", x=nomes, y=scores_v, marker_color="#ffc107"))
    fig_comp.update_layout(barmode="group", yaxis=dict(range=[0, 10]), height=350,
                           margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig_comp, use_container_width=True)


# ====================================================================
# MAIN
# ====================================================================

def main():
    config = render_sidebar()

    # Recalcular scores automaticamente se parâmetros mudaram e há dados em cache
    dados_brutos = st.session_state.get("dados_brutos")
    config_anterior = st.session_state.get("config_anterior", {})
    config_atual = {
        k: v for k, v in config.items()
        if k in ["pesos_qualidade", "pesos_valuation", "peso_q_final",
                 "peso_v_final", "metodo_pj"]
    }

    if dados_brutos and config_anterior and config_atual != config_anterior:
        _recalcular_scores(dados_brutos, config)

    # Navegação por abas
    if st.session_state.get("analise_ok"):
        tab1, tab2, tab3, tab4 = st.tabs([
            "📁 Upload & Análise",
            "🏆 Ranking",
            "🔍 Detalhe",
            "⚖️ Comparação"
        ])
        with tab1:
            tela_upload(config)
        with tab2:
            tela_ranking()
        with tab3:
            tela_detalhe()
        with tab4:
            tela_comparacao()
    else:
        tela_upload(config)


if __name__ == "__main__":
    main()
