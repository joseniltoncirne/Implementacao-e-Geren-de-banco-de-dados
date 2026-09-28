# Bancos de Dados NoSQL — UNIPÊ

Trabalhos da disciplina **Implementação e Gerenciamento de Bancos de Dados NoSQL** (Ciência da Computação, UNIPÊ, 2026.2).

Autor: **Josenilton Cirne Ramalho Neto**

## Trabalhos

Os trabalhos estão separados em duas pastas: **individuais** e **em-grupo** (o Desafio GeoLog, que o enunciado pede em grupo, foi feito individualmente, como explicado no relatório).


| Pasta | Trabalho | O que faz | Tecnologias |
|---|---|---|---|
| [individuais/atividade01-mongodb](individuais/atividade01-mongodb) | Atividade 1 | Importa 25 mil restaurantes de Nova York e faz buscas com filtros | MongoDB, Compass, mongosh |
| [individuais/exercicio01-openf1](individuais/exercicio01-openf1) | Exercício 01 | Coleta dados do GP da Itália de F1 2023 de uma API e salva sem duplicar | Python, requests, pymongo |
| [individuais/exercicio02-cartola](individuais/exercicio02-cartola) | Exercício 2 | Coleta clubes, jogadores e mercado do Cartola FC (ETL) | Python, requests, pymongo |
| [individuais/exercicio03-geojson](individuais/exercicio03-geojson) | Exercício 03 | Salva os 46 mil postos de saúde (UBS) do Brasil em GeoJSON e busca por proximidade | Python, pandas, geopandas, MongoDB 2dsphere |
| [individuais/pratica04-streamlit](individuais/pratica04-streamlit) | Prática 04 | Página web para explorar as voltas da F1 com gráficos | Streamlit, Plotly, MongoDB |
| [individuais/pratica05-poliglota](individuais/pratica05-poliglota) | Prática 05 | A mesma página, salvando resumos de desempenho num segundo banco | Streamlit, MongoDB, SQLite |
| [em-grupo/desafio-geolog](em-grupo/desafio-geolog) | Desafio GeoLog | Monitoramento de caminhões com mapa, busca por raio e painel | Streamlit, Folium, Plotly, MongoDB, SQLite |
| [individuais/lista01-redis](individuais/lista01-redis) | Lista 01 (Redis) | 20 exercícios com os tipos do Redis: textos, objetos, filas, conjuntos, ranking, mensagens e transações | Redis (Memurai), redis-cli, Python |

Cada pasta tem o código, o `requirements.txt`, os prints e o PDF entregue.

## Como rodar

Pré-requisitos: **Python 3** e **MongoDB** rodando em `mongodb://localhost:27017` (e o **Redis/Memurai** em `localhost:6379` para a Lista 01).

```bash
cd individuais/nome-da-pasta      # ou em-grupo/desafio-geolog
python -m pip install -r requirements.txt
```

Depois, o comando de cada trabalho está no README da pasta.
