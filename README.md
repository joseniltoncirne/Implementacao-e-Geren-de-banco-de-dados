# Bancos de Dados NoSQL — UNIPÊ

Trabalhos da disciplina **Implementação e Gerenciamento de Bancos de Dados NoSQL** (Ciência da Computação, UNIPÊ, 2026.2).

Autor: **Josenilton Cirne Ramalho Neto**

## Trabalhos

| Pasta | Trabalho | O que faz | Tecnologias |
|---|---|---|---|
| [atividade01-mongodb](atividade01-mongodb) | Atividade 1 | Importa 25 mil restaurantes de Nova York e faz buscas com filtros | MongoDB, Compass, mongosh |
| [exercicio01-openf1](exercicio01-openf1) | Exercício 01 | Coleta dados do GP da Itália de F1 2023 de uma API e salva sem duplicar | Python, requests, pymongo |
| [exercicio02-cartola](exercicio02-cartola) | Exercício 2 | Coleta clubes, jogadores e mercado do Cartola FC (ETL) | Python, requests, pymongo |
| [exercicio03-geojson](exercicio03-geojson) | Exercício 03 | Salva os 46 mil postos de saúde (UBS) do Brasil em GeoJSON e busca por proximidade | Python, pandas, geopandas, MongoDB 2dsphere |
| [pratica04-streamlit](pratica04-streamlit) | Prática 04 | Página web para explorar as voltas da F1 com gráficos | Streamlit, Plotly, MongoDB |
| [pratica05-poliglota](pratica05-poliglota) | Prática 05 | A mesma página, salvando resumos de desempenho num segundo banco | Streamlit, MongoDB, SQLite |
| [desafio-geolog](desafio-geolog) | Desafio GeoLog | Monitoramento de caminhões com mapa, busca por raio e painel | Streamlit, Folium, Plotly, MongoDB, SQLite |
| [lista01-redis](lista01-redis) | Lista 01 (Redis) | 20 exercícios com os tipos do Redis: textos, objetos, filas, conjuntos, ranking, mensagens e transações | Redis (Memurai), redis-cli, Python |

Cada pasta tem o código, o `requirements.txt`, os prints e o PDF entregue.

## Como rodar

Pré-requisitos: **Python 3** e **MongoDB** rodando em `mongodb://localhost:27017` (e o **Redis/Memurai** em `localhost:6379` para a Lista 01).

```bash
cd nome-da-pasta
python -m pip install -r requirements.txt
```

Depois, o comando de cada trabalho está no README da pasta.
