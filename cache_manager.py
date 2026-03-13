"""
cache_manager.py
Gerencia cache local dos dados fundamentalistas buscados via yfinance.

Regras:
- Cache salvo em 'cache_fundamentalista.json' na pasta do app
- Validade: 7 dias por ticker
- Mudanca no conjunto de tickers (XLSX/CSV) invalida todo o cache
- Botao de forcar atualizacao disponivel na interface
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

CACHE_FILE = "cache_fundamentalista.json"
CACHE_VALIDADE_DIAS = 7


def _carregar_cache_raw() -> dict:
    """Carrega o arquivo de cache do disco. Retorna dict vazio se nao existir."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar_cache_raw(cache: dict):
    """Salva o cache no disco."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"Aviso: nao foi possivel salvar cache: {e}")


def _ticker_expirado(entrada: dict) -> bool:
    """Verifica se a entrada do cache expirou (mais de 7 dias)."""
    try:
        salvo_em = datetime.fromisoformat(entrada.get("salvo_em", "2000-01-01"))
        return datetime.now() - salvo_em > timedelta(days=CACHE_VALIDADE_DIAS)
    except Exception:
        return True


def _gerar_chave_conjunto(tickers: list) -> str:
    """
    Gera uma chave unica para o conjunto de tickers carregado.
    Qualquer mudanca na lista gera uma chave diferente.
    """
    return "|".join(sorted([t.upper().strip() for t in tickers]))


def verificar_cache(empresas: list) -> dict:
    """
    Verifica o estado do cache para o conjunto de empresas.

    Retorna dict com:
    - 'status': 'completo', 'parcial' ou 'vazio'
    - 'tickers_ok': lista de tickers com cache valido
    - 'tickers_faltando': lista de tickers sem cache ou expirados
    - 'data_mais_antiga': data do cache mais antigo entre os validos
    - 'conjunto_mudou': True se o conjunto de tickers mudou desde o ultimo cache
    """
    cache = _carregar_cache_raw()
    tickers_solicitados = [e["ticker"].upper().strip() for e in empresas]
    chave_atual = _gerar_chave_conjunto(tickers_solicitados)

    # Verificar se o conjunto de tickers mudou
    conjunto_salvo = cache.get("_conjunto_tickers", "")
    conjunto_mudou = conjunto_salvo != chave_atual

    tickers_ok = []
    tickers_faltando = []
    datas = []

    dados = cache.get("dados", {})

    for ticker in tickers_solicitados:
        entrada = dados.get(ticker)
        if entrada is None or _ticker_expirado(entrada) or conjunto_mudou:
            tickers_faltando.append(ticker)
        else:
            tickers_ok.append(ticker)
            try:
                datas.append(datetime.fromisoformat(entrada["salvo_em"]))
            except Exception:
                pass

    if not tickers_faltando:
        status = "completo"
    elif not tickers_ok:
        status = "vazio"
    else:
        status = "parcial"

    data_mais_antiga = min(datas).strftime("%d/%m/%Y %H:%M") if datas else None

    return {
        "status": status,
        "tickers_ok": tickers_ok,
        "tickers_faltando": tickers_faltando,
        "data_mais_antiga": data_mais_antiga,
        "conjunto_mudou": conjunto_mudou,
        "chave_atual": chave_atual,
    }


def carregar_do_cache(tickers: list) -> dict:
    """
    Carrega dados do cache para os tickers solicitados.
    Retorna dict indexado por ticker com os dados salvos.
    """
    cache = _carregar_cache_raw()
    dados = cache.get("dados", {})
    resultado = {}

    for ticker in tickers:
        ticker_upper = ticker.upper().strip()
        entrada = dados.get(ticker_upper)
        if entrada and not _ticker_expirado(entrada):
            resultado[ticker_upper] = entrada["data"]

    return resultado


def salvar_no_cache(dados_empresas: dict, chave_conjunto: str):
    """
    Salva dados de empresas no cache.
    dados_empresas: dict indexado por ticker com dados do yfinance
    chave_conjunto: chave do conjunto atual de tickers
    """
    cache = _carregar_cache_raw()

    if "dados" not in cache:
        cache["dados"] = {}

    agora = datetime.now().isoformat()

    for ticker, data in dados_empresas.items():
        ticker_upper = ticker.upper().strip()
        # Salvar apenas empresas com sucesso
        if data.get("success"):
            # Remover indicadores_completos do cache para evitar dados duplicados
            # Eles sao recalculados pelo data_fetcher a partir dos demonstrativos
            cache["dados"][ticker_upper] = {
                "salvo_em": agora,
                "data": _serializar(data)
            }

    # Atualizar chave do conjunto
    cache["_conjunto_tickers"] = chave_conjunto
    cache["_atualizado_em"] = agora

    _salvar_cache_raw(cache)


def limpar_cache():
    """Remove o arquivo de cache completamente."""
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            return True
    except Exception:
        pass
    return False


def info_cache() -> Optional[dict]:
    """Retorna informacoes resumidas sobre o cache atual."""
    if not os.path.exists(CACHE_FILE):
        return None

    cache = _carregar_cache_raw()
    dados = cache.get("dados", {})

    if not dados:
        return None

    tickers_validos = [t for t, v in dados.items() if not _ticker_expirado(v)]
    tickers_expirados = [t for t, v in dados.items() if _ticker_expirado(v)]

    atualizado_em = cache.get("_atualizado_em")
    if atualizado_em:
        try:
            atualizado_em = datetime.fromisoformat(atualizado_em).strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass

    return {
        "total_tickers": len(dados),
        "tickers_validos": len(tickers_validos),
        "tickers_expirados": len(tickers_expirados),
        "atualizado_em": atualizado_em,
        "arquivo": CACHE_FILE,
        "tamanho_kb": round(os.path.getsize(CACHE_FILE) / 1024, 1),
    }


def _serializar(obj):
    """
    Serializa objetos Python para JSON.
    Converte tipos nao serializaveis (numpy, pandas, etc).
    """
    import numpy as np
    import pandas as pd

    if isinstance(obj, dict):
        return {k: _serializar(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serializar(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    elif isinstance(obj, np.ndarray):
        return [_serializar(v) for v in obj.tolist()]
    elif isinstance(obj, pd.DataFrame):
        # Converter índices e colunas Timestamp para string
        df_clean = obj.where(pd.notnull(obj), None).copy()
        df_clean.columns = [c.isoformat() if isinstance(c, (pd.Timestamp, datetime)) else str(c)
                            for c in df_clean.columns]
        df_clean.index = [i.isoformat() if isinstance(i, (pd.Timestamp, datetime)) else str(i)
                          for i in df_clean.index]
        return df_clean.to_dict()
    elif isinstance(obj, pd.Series):
        s_clean = obj.where(pd.notnull(obj), None).copy()
        s_clean.index = [i.isoformat() if isinstance(i, (pd.Timestamp, datetime)) else str(i)
                         for i in s_clean.index]
        return s_clean.to_dict()
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, float) and (obj != obj):  # NaN check
        return None
    else:
        return obj
