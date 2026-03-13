"""
scorer.py
Calcula scores de Qualidade e Valuation para cada empresa.
Todos os scores sao normalizados de 0 a 10.

Limites revisados e validados conforme especificacao:
- 1.1 Rentabilidade: ROE, ROIC, Margem Liquida
- 1.2 Divida: Divida/EBITDA, Divida/PL, Liquidez Corrente
- 1.3 Caixa: FCF consistencia, tendencia, conversao, yield, FCF/Receita
- 1.4 Crescimento: CAGR Receita, Lucro, EBITDA, FCF + consistencia
- 1.5 Eficiencia: Margem Bruta, Margem EBIT, ROA (sem Margem Liquida)
- 2.x Valuation: mantido como estava
"""

import numpy as np
from typing import Optional


# ====================================================================
# UTILITARIOS
# ====================================================================

def _safe(val, default=None):
    """
    Retorna val convertido para float se possivel, senao default.
    Garante que valores vindos do cache JSON (strings numericas)
    sejam corretamente tratados como numeros.
    """
    if val is None:
        return default
    try:
        converted = float(val)
        if np.isnan(converted):
            return default
        return converted
    except Exception:
        return default


def _safe_list(valores: list) -> list:
    """
    Converte todos os elementos de uma lista para float.
    Remove None e NaN — essencial para listas vindas do cache JSON.
    """
    result = []
    for v in (valores or []):
        try:
            f = float(v)
            if not np.isnan(f):
                result.append(f)
        except Exception:
            pass
    return result


def _normalize(valor, minimo, maximo, inverso=False) -> float:
    """
    Normaliza um valor para escala 0-10.
    - maior = melhor: (valor - min) / (max - min) * 10
    - menor = melhor (inverso=True): (max - valor) / (max - min) * 10
    Valores fora dos limites sao clampeados em 0 ou 10.
    """
    if valor is None:
        return 5.0
    valor = float(valor)
    minimo = float(minimo)
    maximo = float(maximo)
    if maximo == minimo:
        return 5.0
    if inverso:
        score = (maximo - valor) / (maximo - minimo) * 10
    else:
        score = (valor - minimo) / (maximo - minimo) * 10
    return max(0.0, min(10.0, score))


def _tendencia(valores: list) -> float:
    """
    Retorna coeficiente de tendencia normalizado (-1 a 1).
    Positivo = crescimento, negativo = queda.
    Valores chegam do mais recente ao mais antigo.
    """
    valores = _safe_list(valores)
    if not valores or len(valores) < 2:
        return 0.0
    vals = list(reversed(valores))
    x = np.arange(len(vals))
    try:
        coef = np.polyfit(x, vals, 1)[0]
        media = np.mean(np.abs(vals))
        if media == 0:
            return 0.0
        return float(np.clip(coef / media, -1.0, 1.0))
    except Exception:
        return 0.0


def _consistencia(valores: list) -> float:
    """
    Retorna score de consistencia (0-1).
    Combina percentual de anos positivos com baixa volatilidade.
    """
    valores = _safe_list(valores)
    if not valores or len(valores) < 2:
        return 0.5
    positivos = sum(1 for v in valores if v > 0)
    pct_positivos = positivos / len(valores)
    cv = np.std(valores) / (abs(np.mean(valores)) + 1e-10)
    consistencia = pct_positivos * (1 / (1 + cv * 0.5))
    return float(np.clip(consistencia, 0.0, 1.0))


def _score_tendencia(valores: list) -> float:
    """Mapeia tendencia (-1..+1) para score (0..10). Crescimento = melhor."""
    tend = _tendencia(valores)
    return (tend + 1) / 2 * 10


def _score_tendencia_inversa(valores: list) -> float:
    """Mapeia tendencia para score invertido. Queda = melhor (ex: divida)."""
    tend = _tendencia(valores)
    return (-tend + 1) / 2 * 10


def _score_consistencia(valores: list) -> float:
    """Mapeia consistencia (0..1) para score (0..10)."""
    return _consistencia(valores) * 10


# ====================================================================
# DIMENSAO 1 — QUALIDADE
# ====================================================================

def score_rentabilidade(ind: dict) -> dict:
    """
    1.1 Rentabilidade Consistente
    Metricas: ROE, ROIC, Margem Liquida — valor atual + tendencia + consistencia
    Limites:
      ROE:           min=-15%,  max=33%
      ROIC:          min=-3%,   max=26%
      Margem Liq.:   min=-9%,   max=40%
    """
    scores = []
    detalhes = {}

    # --- ROE ---
    roe = _safe(ind.get("roe"))
    roe_hist = ind.get("roe_hist", [])

    if roe is not None:
        s = _normalize(roe, -0.15, 0.33)
        scores.append(s)
        detalhes["ROE atual"] = f"{roe*100:.1f}% -> {s:.1f}"

    if len(roe_hist) >= 2:
        s = _score_tendencia(roe_hist)
        scores.append(s)
        detalhes["ROE tendencia"] = f"{s:.1f}"

        s = _score_consistencia(roe_hist)
        scores.append(s)
        detalhes["ROE consistencia"] = f"{s:.1f}"

    # --- ROIC ---
    roic = _safe(ind.get("roic"))
    roic_hist = ind.get("roic_hist", [])

    if roic is not None:
        s = _normalize(roic, -0.03, 0.26)
        scores.append(s)
        detalhes["ROIC atual"] = f"{roic*100:.1f}% -> {s:.1f}"

    if len(roic_hist) >= 2:
        s = _score_tendencia(roic_hist)
        scores.append(s)
        detalhes["ROIC tendencia"] = f"{s:.1f}"

        s = _score_consistencia(roic_hist)
        scores.append(s)
        detalhes["ROIC consistencia"] = f"{s:.1f}"

    # --- Margem Liquida ---
    ml = _safe(ind.get("margem_liquida"))
    ml_hist = ind.get("margens_liquidas_hist", [])

    if ml is not None:
        s = _normalize(ml, -0.09, 0.40)
        scores.append(s)
        detalhes["Margem Liquida atual"] = f"{ml*100:.1f}% -> {s:.1f}"

    if len(ml_hist) >= 2:
        s = _score_tendencia(ml_hist)
        scores.append(s)
        detalhes["Margem Liquida tendencia"] = f"{s:.1f}"

        s = _score_consistencia(ml_hist)
        scores.append(s)
        detalhes["Margem Liquida consistencia"] = f"{s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_metricas": len(scores)}


def score_divida(ind: dict) -> dict:
    """
    1.2 Capacidade de Pagar Dividas
    Metricas: Divida/EBITDA, Divida/PL, Liquidez Corrente
    Limites:
      Divida/EBITDA:     min=0x,   max=5x    (menor = melhor)
      Divida/PL:         min=0,    max=2.5x  (menor = melhor)
      Liquidez corrente: min=0x,   max=3.5x  (maior = melhor)
    """
    scores = []
    detalhes = {}

    # --- Divida/EBITDA ---
    div_ebitda_hist = ind.get("divida_ebitda_hist", [])

    if div_ebitda_hist:
        val = div_ebitda_hist[0]
        s = _normalize(val, 0, 5.0, inverso=True)
        scores.append(s)
        detalhes["Divida/EBITDA atual"] = f"{val:.2f}x -> {s:.1f}"

        if len(div_ebitda_hist) >= 2:
            s = _score_tendencia_inversa(div_ebitda_hist)
            scores.append(s)
            detalhes["Divida/EBITDA tendencia"] = f"{s:.1f}"

    # --- Divida/PL ---
    div_pl = _safe(ind.get("divida_pl"))
    if div_pl is not None:
        div_pl_x = div_pl / 100  # yfinance retorna em %: 61.3 = 0.613x
        s = _normalize(div_pl_x, 0, 2.5, inverso=True)
        scores.append(s)
        detalhes["Divida/PL atual"] = f"{div_pl_x:.2f}x -> {s:.1f}"

    # --- Liquidez Corrente ---
    liq_hist = ind.get("liquidez_corrente_hist", [])

    if liq_hist:
        val = liq_hist[0]
        s = _normalize(val, 0.0, 3.5)
        scores.append(s)
        detalhes["Liquidez Corrente atual"] = f"{val:.2f}x -> {s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_metricas": len(scores)}


def score_caixa(ind: dict) -> dict:
    """
    1.3 Geracao de Caixa Real
    Metricas: FCF consistencia, tendencia, conversao de caixa, FCF Yield, FCF/Receita
    Limites mantidos como especificado.
    """
    scores = []
    detalhes = {}

    fcf_hist = ind.get("fcf_hist", [])

    if fcf_hist:
        s = _score_consistencia(fcf_hist)
        scores.append(s)
        detalhes["FCF consistencia"] = f"{s:.1f}"

        if len(fcf_hist) >= 2:
            s = _score_tendencia(fcf_hist)
            scores.append(s)
            detalhes["FCF tendencia"] = f"{s:.1f}"

    conv_hist = ind.get("conversao_caixa_hist", [])
    if conv_hist:
        val = float(np.mean(conv_hist[:4]))
        s = _normalize(val, 0, 1.5)
        scores.append(s)
        detalhes["Conversao de Caixa media"] = f"{val:.2f}x -> {s:.1f}"

    fcf_yield = _safe(ind.get("fcf_yield"))
    if fcf_yield is not None:
        s = _normalize(fcf_yield, -0.02, 0.10)
        scores.append(s)
        detalhes["FCF Yield"] = f"{fcf_yield*100:.1f}% -> {s:.1f}"

    receitas = ind.get("receitas_hist", [])
    if fcf_hist and receitas:
        n = min(len(fcf_hist), len(receitas))
        fcf_margem = [f/r for f, r in zip(fcf_hist[:n], receitas[:n]) if r != 0]
        if fcf_margem:
            val = float(np.mean(fcf_margem))
            s = _normalize(val, -0.05, 0.20)
            scores.append(s)
            detalhes["FCF/Receita medio"] = f"{val*100:.1f}% -> {s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_metricas": len(scores)}


def score_crescimento(ind: dict) -> dict:
    """
    1.4 Crescimento Sustentavel
    Metricas: CAGR Receita, Lucro, EBITDA, FCF + consistencia crescimento receita
    Limites mantidos como especificado.
    """
    scores = []
    detalhes = {}

    cagr_r = _safe(ind.get("cagr_receita"))
    if cagr_r is not None:
        s = _normalize(cagr_r, -0.05, 0.20)
        scores.append(s)
        detalhes["CAGR Receita"] = f"{cagr_r*100:.1f}% -> {s:.1f}"

    cagr_l = _safe(ind.get("cagr_lucro"))
    if cagr_l is not None:
        s = _normalize(cagr_l, -0.10, 0.30)
        scores.append(s)
        detalhes["CAGR Lucro"] = f"{cagr_l*100:.1f}% -> {s:.1f}"

    cagr_e = _safe(ind.get("cagr_ebitda"))
    if cagr_e is not None:
        s = _normalize(cagr_e, -0.10, 0.25)
        scores.append(s)
        detalhes["CAGR EBITDA"] = f"{cagr_e*100:.1f}% -> {s:.1f}"

    cagr_f = _safe(ind.get("cagr_fcf"))
    if cagr_f is not None:
        s = _normalize(cagr_f, -0.15, 0.30)
        scores.append(s)
        detalhes["CAGR FCF"] = f"{cagr_f*100:.1f}% -> {s:.1f}"

    receitas = ind.get("receitas_hist", [])
    if receitas and len(receitas) >= 2:
        cresc_ano = [
            (receitas[i] - receitas[i+1]) / abs(receitas[i+1])
            for i in range(len(receitas)-1)
            if receitas[i+1] != 0
        ]
        if cresc_ano:
            s = _score_consistencia(cresc_ano)
            scores.append(s)
            detalhes["Consistencia crescimento receita"] = f"{s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_metricas": len(scores)}


def score_eficiencia(ind: dict) -> dict:
    """
    1.5 Eficiencia Operacional
    Metricas: Margem Bruta, Margem EBIT, ROA — valor atual + tendencia + consistencia
    Nota: Margem Liquida foi movida para 1.1 Rentabilidade.
    Limites:
      Margem Bruta:  min=0%,   max=60%
      Margem EBIT:   min=-5%,  max=35%
      ROA:           min=-2%,  max=15%
    """
    scores = []
    detalhes = {}

    # --- Margem Bruta ---
    mb = _safe(ind.get("margem_bruta"))
    mb_hist = ind.get("margens_brutas_hist", [])

    if mb is not None:
        s = _normalize(mb, 0.0, 0.60)
        scores.append(s)
        detalhes["Margem Bruta atual"] = f"{mb*100:.1f}% -> {s:.1f}"

    if len(mb_hist) >= 2:
        s = _score_tendencia(mb_hist)
        scores.append(s)
        detalhes["Margem Bruta tendencia"] = f"{s:.1f}"

        s = _score_consistencia(mb_hist)
        scores.append(s)
        detalhes["Margem Bruta consistencia"] = f"{s:.1f}"

    # --- Margem EBIT ---
    me_hist = ind.get("margens_ebit_hist", [])
    me = me_hist[0] if me_hist else _safe(ind.get("margem_ebit"))

    if me is not None:
        s = _normalize(me, -0.05, 0.35)
        scores.append(s)
        detalhes["Margem EBIT atual"] = f"{me*100:.1f}% -> {s:.1f}"

    if len(me_hist) >= 2:
        s = _score_tendencia(me_hist)
        scores.append(s)
        detalhes["Margem EBIT tendencia"] = f"{s:.1f}"

        s = _score_consistencia(me_hist)
        scores.append(s)
        detalhes["Margem EBIT consistencia"] = f"{s:.1f}"

    # --- ROA ---
    roa = _safe(ind.get("roa"))
    roa_hist = ind.get("roa_hist", [])

    if roa is not None:
        s = _normalize(roa, -0.02, 0.15)
        scores.append(s)
        detalhes["ROA atual"] = f"{roa*100:.1f}% -> {s:.1f}"

    if len(roa_hist) >= 2:
        s = _score_tendencia(roa_hist)
        scores.append(s)
        detalhes["ROA tendencia"] = f"{s:.1f}"

        s = _score_consistencia(roa_hist)
        scores.append(s)
        detalhes["ROA consistencia"] = f"{s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_metricas": len(scores)}


def score_qualidade(ind: dict, pesos: dict) -> dict:
    """
    Score composto de Qualidade.
    pesos: dict com keys rentabilidade, divida, caixa, crescimento, eficiencia (somam 1.0)
    Cada sub-score ja esta em escala 0-10 antes de aplicar os pesos.
    """
    r = score_rentabilidade(ind)
    d = score_divida(ind)
    c = score_caixa(ind)
    g = score_crescimento(ind)
    e = score_eficiencia(ind)

    w_r = pesos.get("rentabilidade", 0.15)
    w_d = pesos.get("divida", 0.25)
    w_c = pesos.get("caixa", 0.25)
    w_g = pesos.get("crescimento", 0.15)
    w_e = pesos.get("eficiencia", 0.20)

    total = (r["score"] * w_r + d["score"] * w_d + c["score"] * w_c +
             g["score"] * w_g + e["score"] * w_e)

    return {
        "score_qualidade": round(total, 2),
        "sub_scores": {
            "rentabilidade": r,
            "divida": d,
            "caixa": c,
            "crescimento": g,
            "eficiencia": e,
        }
    }


# ====================================================================
# DIMENSAO 2 — VALUATION (mantida como estava)
# ====================================================================

def calcular_preco_justo_graham(ind: dict) -> Optional[float]:
    """Formula de Benjamin Graham: P = sqrt(22.5 x EPS x VPA)"""
    eps = _safe(ind.get("eps"))
    vpa = _safe(ind.get("book_value"))
    if eps is None or vpa is None or eps <= 0 or vpa <= 0:
        return None
    try:
        return (22.5 * eps * vpa) ** 0.5
    except Exception:
        return None


def calcular_preco_justo_dcf(ind: dict, taxa_desconto: float = 0.12,
                              anos: int = 10, crescimento_perpetuidade: float = 0.03) -> Optional[float]:
    """
    DCF simplificado baseado em FCF historico e crescimento estimado.
    Fase 1: crescimento estimado nos primeiros 5 anos
    Fase 2: metade do crescimento nos ultimos 5 anos
    Valor terminal pela perpetuidade de Gordon
    """
    fcf_hist = ind.get("fcf_hist", [])
    shares = _safe(ind.get("shares"))

    if not fcf_hist or shares is None or shares <= 0:
        return None

    fcf_base = fcf_hist[0]
    if fcf_base <= 0:
        return None

    cresc = _safe(ind.get("cresc_estimado")) or 0.05
    cresc = min(max(cresc, -0.05), 0.25)

    try:
        fcf_projetado = []
        for i in range(anos):
            taxa = cresc if i < 5 else cresc * 0.5
            fcf_i = fcf_hist[0] * ((1 + taxa) ** (i + 1))
            fcf_projetado.append(fcf_i)

        vp_fcfs = sum([f / ((1 + taxa_desconto) ** (i + 1))
                       for i, f in enumerate(fcf_projetado)])

        fcf_terminal = fcf_projetado[-1] * (1 + crescimento_perpetuidade)
        vt = fcf_terminal / (taxa_desconto - crescimento_perpetuidade)
        vp_terminal = vt / ((1 + taxa_desconto) ** anos)

        return (vp_fcfs + vp_terminal) / shares

    except Exception:
        return None


def score_valuation_absoluto(ind: dict, metodo: str = "media") -> dict:
    """Score de valuation absoluto: preco atual vs. preco justo."""
    preco = _safe(ind.get("preco_atual"))
    detalhes = {}

    if preco is None or preco <= 0:
        return {"score": 5.0, "detalhes": {"aviso": "Preco nao disponivel"}, "upside": None}

    pj_graham = calcular_preco_justo_graham(ind)
    pj_dcf = calcular_preco_justo_dcf(ind)

    detalhes["Preco atual"] = f"R$ {preco:.2f}"
    if pj_graham:
        detalhes["Preco justo Graham"] = f"R$ {pj_graham:.2f}"
    if pj_dcf:
        detalhes["Preco justo DCF"] = f"R$ {pj_dcf:.2f}"

    if metodo == "graham":
        pj = pj_graham
    elif metodo == "dcf":
        pj = pj_dcf
    else:
        validos = [p for p in [pj_graham, pj_dcf] if p is not None]
        pj = float(np.mean(validos)) if validos else None

    if pj is None:
        return {"score": 5.0, "detalhes": detalhes, "upside": None}

    upside = (pj - preco) / preco
    detalhes["Upside estimado"] = f"{upside*100:.1f}%"
    score = _normalize(upside, -0.30, 0.50)

    return {"score": round(score, 2), "detalhes": detalhes, "upside": upside, "preco_justo": pj}


def score_multiplos_historicos(ind: dict) -> dict:
    """Compara multiplos atuais com benchmarks de referencia."""
    scores = []
    detalhes = {}

    pl_atual     = _safe(ind.get("pl"))
    pvp_atual    = _safe(ind.get("pvp"))
    ev_ebitda    = _safe(ind.get("ev_ebitda"))
    pl_fw        = _safe(ind.get("pl_forward"))

    if pl_atual is not None and pl_atual > 0:
        s = _normalize(pl_atual, 5, 35, inverso=True)
        scores.append(s)
        detalhes["P/L atual"] = f"{pl_atual:.1f}x -> {s:.1f}"

    if pvp_atual is not None and pvp_atual > 0:
        s = _normalize(pvp_atual, 0.5, 5.0, inverso=True)
        scores.append(s)
        detalhes["P/VP atual"] = f"{pvp_atual:.1f}x -> {s:.1f}"

    if ev_ebitda is not None and ev_ebitda > 0:
        s = _normalize(ev_ebitda, 3, 20, inverso=True)
        scores.append(s)
        detalhes["EV/EBITDA atual"] = f"{ev_ebitda:.1f}x -> {s:.1f}"

    if pl_atual and pl_fw and pl_atual > 0:
        razao = pl_fw / pl_atual
        s = _normalize(razao, 0.5, 1.5, inverso=True)
        scores.append(s)
        detalhes["P/L Forward vs Trailing"] = f"{razao:.2f}x -> {s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_metricas": len(scores)}


def score_multiplos_setor(ind: dict, empresas_setor: list) -> dict:
    """Compara multiplos da empresa com a mediana do setor."""
    scores = []
    detalhes = {}

    if not empresas_setor:
        return {"score": 5.0, "detalhes": {"aviso": "Sem empresas do setor para comparar"}, "n_peers": 0}

    def mediana_setor(campo):
        vals = [float(e.get(campo)) for e in empresas_setor
                if _safe(e.get(campo)) is not None and float(e.get(campo)) > 0]
        return float(np.median(vals)) if vals else None

    for campo, label in [("pl", "P/L"), ("pvp", "P/VP"), ("ev_ebitda", "EV/EBITDA")]:
        val = _safe(ind.get(campo))
        med = mediana_setor(campo)
        if val and med and med > 0:
            razao = val / med
            s = _normalize(razao, 0.3, 2.0, inverso=True)
            scores.append(s)
            detalhes[f"{label} vs Mediana Setor"] = f"{val:.1f}x vs {med:.1f}x -> {s:.1f}"

    final = float(np.mean(scores)) if scores else 5.0
    return {"score": round(final, 2), "detalhes": detalhes, "n_peers": len(empresas_setor)}


def score_valuation(ind: dict, pesos: dict, metodo_pj: str,
                    empresas_setor: list = None) -> dict:
    """Score composto de Valuation. Cada sub-score ja esta em escala 0-10."""
    abs_score   = score_valuation_absoluto(ind, metodo=metodo_pj)
    hist_score  = score_multiplos_historicos(ind)
    setor_score = score_multiplos_setor(ind, empresas_setor or [])

    w_abs  = pesos.get("absoluto", 0.35)
    w_hist = pesos.get("historico", 0.35)
    w_set  = pesos.get("setor", 0.30)

    total = (abs_score["score"]   * w_abs +
             hist_score["score"]  * w_hist +
             setor_score["score"] * w_set)

    return {
        "score_valuation": round(total, 2),
        "sub_scores": {
            "absoluto": abs_score,
            "historico": hist_score,
            "setor": setor_score,
        }
    }


# ====================================================================
# SCORE FINAL
# ====================================================================

def calcular_score_final(indicadores: dict, pesos_qualidade: dict,
                         pesos_valuation: dict, peso_qualidade_final: float,
                         peso_valuation_final: float, metodo_pj: str,
                         empresas_setor: list = None) -> dict:
    """Calcula o score final completo de uma empresa."""
    q = score_qualidade(indicadores, pesos_qualidade)
    v = score_valuation(indicadores, pesos_valuation, metodo_pj, empresas_setor)

    total_peso = peso_qualidade_final + peso_valuation_final
    w_q = peso_qualidade_final / total_peso
    w_v = peso_valuation_final / total_peso

    score_final = q["score_qualidade"] * w_q + v["score_valuation"] * w_v

    return {
        "score_final": round(score_final, 2),
        "score_qualidade": q["score_qualidade"],
        "score_valuation": v["score_valuation"],
        "detalhes_qualidade": q["sub_scores"],
        "detalhes_valuation": v["sub_scores"],
        "upside": v["sub_scores"]["absoluto"].get("upside"),
        "preco_justo": v["sub_scores"]["absoluto"].get("preco_justo"),
    }


def calcular_todos_scores(dados_empresas: dict, pesos_qualidade: dict,
                          pesos_valuation: dict, peso_q_final: float,
                          peso_v_final: float, metodo_pj: str) -> dict:
    """Calcula scores para todas as empresas considerando comparacao setorial."""
    resultados = {}

    # Agrupar indicadores por setor
    setores = {}
    for ticker, data in dados_empresas.items():
        if not data["success"]:
            continue
        setor = data.get("setor_usuario", "Outros")
        if setor not in setores:
            setores[setor] = []
        setores[setor].append(data["indicators"])

    # Calcular scores
    for ticker, data in dados_empresas.items():
        if not data["success"]:
            resultados[ticker] = {
                "ticker": ticker,
                "nome": data.get("nome_usuario", ticker),
                "setor": data.get("setor_usuario", ""),
                "erro": data.get("error", "Dados indisponiveis"),
                "score_final": None,
                "score_qualidade": None,
                "score_valuation": None,
            }
            continue

        ind = data["indicators"]
        setor = data.get("setor_usuario", "Outros")
        peers = [e for e in setores.get(setor, []) if e is not ind]

        scores = calcular_score_final(
            indicadores=ind,
            pesos_qualidade=pesos_qualidade,
            pesos_valuation=pesos_valuation,
            peso_qualidade_final=peso_q_final,
            peso_valuation_final=peso_v_final,
            metodo_pj=metodo_pj,
            empresas_setor=peers
        )

        resultados[ticker] = {
            "ticker": ticker,
            "nome": data.get("nome_usuario", ticker),
            "setor": setor,
            "preco_atual": ind.get("preco_atual"),
            "market_cap": ind.get("market_cap"),
            "pl": ind.get("pl"),
            "pvp": ind.get("pvp"),
            "ev_ebitda": ind.get("ev_ebitda"),
            "roe": ind.get("roe"),
            "roic": ind.get("roic"),
            "margem_liquida": ind.get("margem_liquida"),
            "dividend_yield": ind.get("dividend_yield"),
            "divida_pl": ind.get("divida_pl"),
            **scores,
            "indicadores_completos": ind,
        }

    return resultados
