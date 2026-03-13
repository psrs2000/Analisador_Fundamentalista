# 📊 Analisador Fundamentalista

## Instalação

```bash
pip install -r requirements.txt
```

## Como usar

```bash
streamlit run app.py
```

O app abrirá automaticamente no navegador em http://localhost:8501

## Estrutura dos arquivos

```
app.py              → Interface Streamlit (telas)
data_fetcher.py     → Busca dados via yfinance
scorer.py           → Cálculo de scores e ranking
requirements.txt    → Dependências Python
```

## Formato do arquivo de entrada (CSV ou XLSX)

| ticker   | nome          | setor          |
|----------|---------------|----------------|
| VALE3.SA | Vale          | Mineração      |
| PETR4.SA | Petrobras     | Petróleo e Gás |
| ITUB4.SA | Itaú Unibanco | Bancos         |
| AAPL     | Apple         | Tecnologia     |

- Ações brasileiras: usar sufixo `.SA` (ex: VALE3.SA)
- Ações americanas: ticker direto (ex: AAPL, MSFT)
- Limite: 50 empresas por análise

## Telas disponíveis

1. **Upload & Análise** — carrega o arquivo e dispara a análise
2. **Ranking** — tabela com scores + mapa Qualidade × Valuation
3. **Detalhe** — todos os indicadores + gauges + gráficos históricos
4. **Comparação** — radar chart + tabela lado a lado

## Configurações (sidebar)

- Pesos de cada critério de Qualidade (devem somar 100%)
- Pesos de cada critério de Valuation (devem somar 100%)
- Peso de Qualidade vs. Valuation no Score Final
- Método de preço justo: Graham, DCF ou Média dos dois
