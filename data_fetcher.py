"""
data_fetcher.py
Busca e processa dados fundamentalistas via yfinance.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional


def fetch_company_data(ticker: str) -> dict:
    """
    Busca todos os dados fundamentalistas de uma empresa via yfinance.
    Retorna dicionário com info, demonstrativos e indicadores calculados.
    """
    result = {
        "ticker": ticker,
        "success": False,
        "error": None,
        "info": {},
        "financials": None,
        "balance_sheet": None,
        "cashflow": None,
        "quarterly_financials": None,
        "quarterly_balance_sheet": None,
        "quarterly_cashflow": None,
        "indicators": {}
    }

    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            result["error"] = "Ticker não encontrado ou sem dados disponíveis"
            return result

        result["info"] = info

        # Demonstrativos anuais
        try:
            result["financials"] = t.financials
        except Exception:
            result["financials"] = None

        try:
            result["balance_sheet"] = t.balance_sheet
        except Exception:
            result["balance_sheet"] = None

        try:
            result["cashflow"] = t.cashflow
        except Exception:
            result["cashflow"] = None

        # Demonstrativos trimestrais
        try:
            result["quarterly_financials"] = t.quarterly_financials
        except Exception:
            result["quarterly_financials"] = None

        try:
            result["quarterly_balance_sheet"] = t.quarterly_balance_sheet
        except Exception:
            result["quarterly_balance_sheet"] = None

        try:
            result["quarterly_cashflow"] = t.quarterly_cashflow
        except Exception:
            result["quarterly_cashflow"] = None

        # Calcular indicadores derivados
        result["indicators"] = _calculate_indicators(result)
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def _get_row(df: pd.DataFrame, keys: list) -> Optional[pd.Series]:
    """Tenta obter uma linha do DataFrame por múltiplos nomes possíveis."""
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            return df.loc[key]
    return None


def _safe_values(series: Optional[pd.Series], n: int = 4) -> list:
    """Retorna os n valores mais recentes de uma série, sem NaN."""
    if series is None:
        return []
    vals = series.dropna().values[:n]
    return [float(v) for v in vals if v is not None]


def _calculate_indicators(data: dict) -> dict:
    """
    Calcula todos os indicadores necessários para os scores.
    """
    ind = {}
    info = data.get("info", {})
    fin = data.get("financials")
    bs = data.get("balance_sheet")
    cf = data.get("cashflow")

    # ----------------------------------------------------------------
    # INDICADORES DIRETOS DO INFO
    # ----------------------------------------------------------------
    ind["nome"]             = info.get("longName", "")
    ind["preco_atual"]      = info.get("currentPrice") or info.get("regularMarketPrice")
    ind["market_cap"]       = info.get("marketCap")
    ind["setor_yahoo"]      = info.get("sector", "")
    ind["industria"]        = info.get("industry", "")
    ind["beta"]             = info.get("beta")
    ind["shares"]           = info.get("sharesOutstanding")

    # Múltiplos atuais
    ind["pl"]               = info.get("trailingPE")
    ind["pl_forward"]       = info.get("forwardPE")
    ind["pvp"]              = info.get("priceToBook")
    ind["ev_ebitda"]        = info.get("enterpriseToEbitda")
    ind["ev_receita"]       = info.get("enterpriseToRevenue")
    # Dividend Yield — alguns tickers BR retornam em % (ex: 14.18) em vez de decimal (0.1418)
    # Usamos trailingAnnualDividendYield como referência — ele sempre vem em decimal
    dy_raw = info.get("dividendYield")
    dy_trailing = info.get("trailingAnnualDividendYield")
    if dy_raw is not None:
        if dy_trailing is not None and dy_trailing > 0 and dy_trailing < 1:
            # Se dy_raw for ~100x maior que dy_trailing, está em percentual
            ratio = dy_raw / dy_trailing
            if 80 <= ratio <= 120:
                ind["dividend_yield"] = dy_raw / 100
            else:
                ind["dividend_yield"] = dy_raw
        else:
            ind["dividend_yield"] = dy_raw
    else:
        ind["dividend_yield"] = dy_trailing  # fallback

    # Margens diretas do info
    ind["margem_bruta"]     = info.get("grossMargins")
    ind["margem_ebit"]      = info.get("ebitdaMargins")
    ind["margem_liquida"]   = info.get("profitMargins")

    # Rentabilidade direta
    ind["roe"]              = info.get("returnOnEquity")
    ind["roa"]              = info.get("returnOnAssets")

    # Crescimento direto
    ind["cresc_receita"]    = info.get("revenueGrowth")
    ind["cresc_lucro"]      = info.get("earningsGrowth")

    # Dívida
    ind["divida_pl"]        = info.get("debtToEquity")

    # ----------------------------------------------------------------
    # SÉRIES HISTÓRICAS (4 ANOS) — DRE
    # ----------------------------------------------------------------
    receitas     = _safe_values(_get_row(fin, ["Total Revenue", "Operating Revenue"]))
    lucros       = _safe_values(_get_row(fin, ["Net Income", "Net Income Common Stockholders"]))
    ebitda_vals  = _safe_values(_get_row(fin, ["EBITDA", "Normalized EBITDA"]))
    ebit_vals    = _safe_values(_get_row(fin, ["EBIT", "Operating Income"]))
    gross_profit = _safe_values(_get_row(fin, ["Gross Profit"]))
    custos       = _safe_values(_get_row(fin, ["Cost Of Revenue"]))

    ind["receitas_hist"]    = receitas
    ind["lucros_hist"]      = lucros
    ind["ebitda_hist"]      = ebitda_vals
    ind["ebit_hist"]        = ebit_vals

    # Margens históricas calculadas
    if receitas and gross_profit and len(receitas) == len(gross_profit):
        ind["margens_brutas_hist"] = [g/r for g, r in zip(gross_profit, receitas) if r != 0]
    else:
        ind["margens_brutas_hist"] = []

    if receitas and lucros and len(receitas) >= len(lucros):
        n = len(lucros)
        ind["margens_liquidas_hist"] = [l/r for l, r in zip(lucros, receitas[:n]) if r != 0]
    else:
        ind["margens_liquidas_hist"] = []

    if receitas and ebit_vals and len(receitas) >= len(ebit_vals):
        n = len(ebit_vals)
        ind["margens_ebit_hist"] = [e/r for e, r in zip(ebit_vals, receitas[:n]) if r != 0]
    else:
        ind["margens_ebit_hist"] = []

    # ----------------------------------------------------------------
    # SÉRIES HISTÓRICAS — BALANÇO
    # ----------------------------------------------------------------
    total_assets    = _safe_values(_get_row(bs, ["Total Assets"]))
    equity          = _safe_values(_get_row(bs, ["Common Stock Equity", "Stockholders Equity"]))
    total_debt      = _safe_values(_get_row(bs, ["Total Debt"]))
    net_debt        = _safe_values(_get_row(bs, ["Net Debt"]))
    cash            = _safe_values(_get_row(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]))
    current_assets  = _safe_values(_get_row(bs, ["Current Assets"]))
    current_liab    = _safe_values(_get_row(bs, ["Current Liabilities"]))

    ind["equity_hist"]          = equity
    ind["total_debt_hist"]      = total_debt
    ind["net_debt_hist"]        = net_debt
    ind["cash_hist"]            = cash
    ind["total_assets_hist"]    = total_assets

    # ROE histórico
    if lucros and equity:
        n = min(len(lucros), len(equity))
        ind["roe_hist"] = [l/e for l, e in zip(lucros[:n], equity[:n]) if e != 0]
    else:
        ind["roe_hist"] = []

    # ROA histórico
    if lucros and total_assets:
        n = min(len(lucros), len(total_assets))
        ind["roa_hist"] = [l/a for l, a in zip(lucros[:n], total_assets[:n]) if a != 0]
    else:
        ind["roa_hist"] = []

    # ROIC histórico
    # ROIC = NOPAT / Capital Investido
    # NOPAT = EBIT x (1 - aliquota de imposto)
    # Capital Investido = PL + Divida Total - Caixa
    tax_rate = _safe_values(_get_row(fin, ["Tax Rate For Calcs"]))
    if ebit_vals and equity and total_debt and cash and tax_rate:
        n = min(len(ebit_vals), len(equity), len(total_debt), len(cash), len(tax_rate))
        roic_hist = []
        for i in range(n):
            try:
                nopat = ebit_vals[i] * (1 - tax_rate[i])
                capital_investido = equity[i] + total_debt[i] - cash[i]
                if capital_investido != 0:
                    roic_hist.append(nopat / capital_investido)
                else:
                    roic_hist.append(None)
            except Exception:
                roic_hist.append(None)
        ind["roic_hist"] = [r for r in roic_hist if r is not None]
    else:
        ind["roic_hist"] = []

    # ROIC atual (ano mais recente)
    ind["roic"] = ind["roic_hist"][0] if ind["roic_hist"] else None

    # Divida/EBITDA historico
    if total_debt and ebitda_vals:
        n = min(len(total_debt), len(ebitda_vals))
        ind["divida_ebitda_hist"] = [d/e for d, e in zip(total_debt[:n], ebitda_vals[:n]) if e != 0]
    else:
        ind["divida_ebitda_hist"] = []

    # Liquidez corrente histórica
    if current_assets and current_liab:
        n = min(len(current_assets), len(current_liab))
        ind["liquidez_corrente_hist"] = [a/l for a, l in zip(current_assets[:n], current_liab[:n]) if l != 0]
    else:
        ind["liquidez_corrente_hist"] = []

    # ----------------------------------------------------------------
    # SÉRIES HISTÓRICAS — FLUXO DE CAIXA
    # ----------------------------------------------------------------
    op_cf       = _safe_values(_get_row(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]))
    capex       = _safe_values(_get_row(cf, ["Capital Expenditure", "Capital Expenditure Reported"]))
    fcf         = _safe_values(_get_row(cf, ["Free Cash Flow"]))

    ind["op_cf_hist"]   = op_cf
    ind["capex_hist"]   = [abs(c) for c in capex]  # capex é negativo no yfinance
    ind["fcf_hist"]     = fcf

    # FCF calculado se não vier direto
    if not fcf and op_cf and capex:
        n = min(len(op_cf), len(capex))
        ind["fcf_hist"] = [o + c for o, c in zip(op_cf[:n], capex[:n])]  # capex já é negativo

    # FCF Yield = FCF / Market Cap
    if ind["fcf_hist"] and ind["market_cap"]:
        ind["fcf_yield"] = ind["fcf_hist"][0] / ind["market_cap"]
    else:
        ind["fcf_yield"] = None

    # Conversão de caixa = FCF / Lucro Líquido
    if ind["fcf_hist"] and lucros:
        ind["conversao_caixa_hist"] = [
            f/l for f, l in zip(ind["fcf_hist"], lucros) if l != 0
        ]
    else:
        ind["conversao_caixa_hist"] = []

    # ----------------------------------------------------------------
    # CRESCIMENTO HISTÓRICO (CAGR)
    # ----------------------------------------------------------------
    ind["cagr_receita"] = _calc_cagr(receitas)
    ind["cagr_lucro"]   = _calc_cagr(lucros)
    ind["cagr_ebitda"]  = _calc_cagr(ebitda_vals)
    ind["cagr_fcf"]     = _calc_cagr(ind["fcf_hist"])

    # ----------------------------------------------------------------
    # DADOS PARA VALUATION
    # ----------------------------------------------------------------
    # EPS para Graham e DCF
    ind["eps"]          = info.get("trailingEps")
    ind["eps_forward"]  = info.get("forwardEps")
    ind["book_value"]   = info.get("bookValue")

    # Crescimento estimado para DCF (usa histórico se não tiver estimativa)
    ind["cresc_estimado"] = info.get("earningsGrowth") or ind["cagr_lucro"]

    return ind


def _calc_cagr(values: list) -> Optional[float]:
    """Calcula CAGR dado uma lista de valores do mais recente ao mais antigo."""
    if not values or len(values) < 2:
        return None
    v_final = values[0]
    v_inicial = values[-1]
    n = len(values) - 1
    if v_inicial <= 0 or v_final <= 0:
        return None
    try:
        return (v_final / v_inicial) ** (1 / n) - 1
    except Exception:
        return None


def fetch_all_companies(empresas: list) -> dict:
    """
    Busca dados de todas as empresas da lista.
    empresas: lista de dicts com keys 'ticker', 'nome', 'setor'
    Retorna dict indexado por ticker.
    """
    resultados = {}
    for emp in empresas:
        ticker = emp["ticker"]
        data = fetch_company_data(ticker)
        data["nome_usuario"] = emp.get("nome", ticker)
        data["setor_usuario"] = emp.get("setor", "")
        resultados[ticker] = data
    return resultados
