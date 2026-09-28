import math
import random
import sqlite3
from datetime import datetime, timedelta

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from pymongo import MongoClient, GEOSPHERE, ASCENDING, DESCENDING
from streamlit_folium import st_folium

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "geolog_db"
MONGO_COLECAO = "telemetria"
SQLITE_DB = "logitech.db"
LIMITE_VELOCIDADE = 80

MOTORISTAS = [
    (1, "Carlos Andrade", "123456789", "Ativo"),
    (2, "Mariana Silva", "987654321", "Ativo"),
    (3, "Roberto Souza", "456789123", "Em Descanso"),
]

VEICULOS = [
    (101, "ABC-1A23", "Volvo FH 540", 1),
    (102, "XYZ-9876", "Scania R450", 2),
    (103, "KGB-4567", "Mercedes Actros", 3),
]

TELEMETRIA_SEED = [
    {"veiculo_id": 101, "location": {"type": "Point", "coordinates": [-34.873, -7.115]},
     "temperatura": 4.2, "velocidade": 65, "timestamp": "2026-09-11T10:00:00Z"},
    {"veiculo_id": 102, "location": {"type": "Point", "coordinates": [-34.832, -7.121]},
     "temperatura": -18.5, "velocidade": 85, "timestamp": "2026-09-11T10:05:00Z"},
    {"veiculo_id": 103, "location": {"type": "Point", "coordinates": [-34.950, -7.150]},
     "temperatura": 22.0, "velocidade": 0, "timestamp": "2026-09-11T09:45:00Z"},
]

PONTOS_DE_APOIO = {
    "Base LogiTech - Centro": (-7.1195, -34.8800),
    "Ponto de Apoio - Tambaú": (-7.1080, -34.8260),
    "Ponto de Apoio - BR-230 (Tibiri)": (-7.1500, -34.9450),
}


def para_data(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).replace(tzinfo=None)


@st.cache_resource
def iniciar_sqlite():
    conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS motoristas (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            cnh TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY,
            placa TEXT NOT NULL UNIQUE,
            modelo TEXT NOT NULL,
            motorista_id INTEGER NOT NULL REFERENCES motoristas(id)
        )""")
    conn.executemany("INSERT OR IGNORE INTO motoristas VALUES (?, ?, ?, ?)", MOTORISTAS)
    conn.executemany("INSERT OR IGNORE INTO veiculos VALUES (?, ?, ?, ?)", VEICULOS)
    conn.commit()
    return conn


def gerar_historico(leitura, pontos=6, minutos=10):
    lon, lat = leitura["location"]["coordinates"]
    fim = para_data(leitura["timestamp"])
    historico = []
    passo = 0 if leitura["velocidade"] == 0 else 1
    for i in range(pontos, 0, -1):
        historico.append({
            "veiculo_id": leitura["veiculo_id"],
            "location": {"type": "Point", "coordinates": [round(lon - 0.004 * i * passo, 6), round(lat + 0.002 * i * passo, 6)]},
            "temperatura": round(leitura["temperatura"] + random.uniform(-1.5, 1.5), 1),
            "velocidade": max(0, round(leitura["velocidade"] + random.uniform(-12, 12))) if leitura["velocidade"] else 0,
            "timestamp": fim - timedelta(minutes=minutos * i),
        })
    historico.append({**leitura, "timestamp": fim})
    return historico


@st.cache_resource
def iniciar_mongodb():
    colecao = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)[MONGO_DB][MONGO_COLECAO]
    colecao.create_index([("location", GEOSPHERE)])
    colecao.create_index([("veiculo_id", ASCENDING), ("timestamp", DESCENDING)])
    if colecao.count_documents({}) == 0:
        documentos = [doc for leitura in TELEMETRIA_SEED for doc in gerar_historico(leitura)]
        colecao.insert_many(documentos)
    return colecao


def carregar_cadastro(conn):
    return pd.read_sql("""
        SELECT v.id AS veiculo_id, v.placa, v.modelo,
               m.nome AS motorista, m.cnh, m.status
        FROM veiculos v
        JOIN motoristas m ON m.id = v.motorista_id
        ORDER BY v.id""", conn)


def ultimas_leituras(colecao):
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$veiculo_id", "leitura": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$leitura"}},
    ]
    return list(colecao.aggregate(pipeline))


def veiculos_no_raio(colecao, ultimas, lat, lon, raio_km):
    ids_ultimas = [doc["_id"] for doc in ultimas]
    return list(colecao.find({
        "_id": {"$in": ids_ultimas},
        "location": {"$near": {
            "$geometry": {"type": "Point", "coordinates": [lon, lat]},
            "$maxDistance": raio_km * 1000,
        }},
    }))


def metricas_por_veiculo(colecao):
    pipeline = [
        {"$group": {
            "_id": "$veiculo_id",
            "leituras": {"$sum": 1},
            "temperatura_media": {"$avg": "$temperatura"},
            "temperatura_min": {"$min": "$temperatura"},
            "temperatura_max": {"$max": "$temperatura"},
            "velocidade_max": {"$max": "$velocidade"},
        }},
        {"$sort": {"_id": 1}},
    ]
    return pd.DataFrame(list(colecao.aggregate(pipeline))).rename(columns={"_id": "veiculo_id"})


def historico_telemetria(colecao):
    docs = list(colecao.find({}, {"_id": 0}).sort("timestamp", 1))
    df = pd.DataFrame(docs)
    if not df.empty:
        df["longitude"] = df["location"].apply(lambda loc: loc["coordinates"][0])
        df["latitude"] = df["location"].apply(lambda loc: loc["coordinates"][1])
    return df


def distancia_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def visao_unificada(cadastro, ultimas):
    telemetria = pd.DataFrame([{
        "veiculo_id": d["veiculo_id"],
        "temperatura": d["temperatura"],
        "velocidade": d["velocidade"],
        "latitude": d["location"]["coordinates"][1],
        "longitude": d["location"]["coordinates"][0],
        "timestamp": d["timestamp"],
    } for d in ultimas])
    return cadastro.merge(telemetria, on="veiculo_id", how="left")


def simular_movimentacao(colecao, ultimas):
    agora = max(d["timestamp"] for d in ultimas) + timedelta(minutes=5)
    novos = []
    for d in ultimas:
        lon, lat = d["location"]["coordinates"]
        parado = d["velocidade"] == 0 and random.random() < 0.5
        passo = 0 if parado else 0.006
        novos.append({
            "veiculo_id": d["veiculo_id"],
            "location": {"type": "Point", "coordinates": [
                round(lon + random.uniform(-passo, passo), 6),
                round(lat + random.uniform(-passo, passo), 6),
            ]},
            "temperatura": round(d["temperatura"] + random.uniform(-0.8, 0.8), 1),
            "velocidade": 0 if parado else int(min(110, max(20, d["velocidade"] + random.uniform(-15, 20)))),
            "timestamp": agora,
        })
    colecao.insert_many(novos)
    return len(novos)


def cor_do_veiculo(linha, dentro_do_raio):
    if linha["velocidade"] > LIMITE_VELOCIDADE:
        return "red"
    return "green" if dentro_do_raio else "gray"


def montar_mapa(lat, lon, raio_km, nome_ponto, unificada, ids_no_raio, historico):
    mapa = folium.Map(location=[lat, lon], zoom_start=12, tiles="OpenStreetMap")
    folium.Circle([lat, lon], radius=raio_km * 1000, color="#1f77b4", fill=True,
                  fill_opacity=0.08, tooltip=f"Raio de busca: {raio_km} km").add_to(mapa)
    folium.Marker([lat, lon], tooltip=nome_ponto,
                  icon=folium.Icon(color="blue", icon="home")).add_to(mapa)
    for _, v in unificada.iterrows():
        rota = historico[historico["veiculo_id"] == v["veiculo_id"]][["latitude", "longitude"]].values.tolist()
        if len(rota) > 1:
            folium.PolyLine(rota, color="#555555", weight=3, opacity=0.6,
                            tooltip=f"Rota {v['placa']}").add_to(mapa)
        dentro = v["veiculo_id"] in ids_no_raio
        folium.Marker(
            [v["latitude"], v["longitude"]],
            tooltip=f"{v['placa']} - {v['motorista']}",
            popup=folium.Popup(
                f"<b>{v['placa']}</b> ({v['modelo']})<br>Motorista: {v['motorista']}<br>"
                f"Temperatura: {v['temperatura']} °C<br>Velocidade: {v['velocidade']} km/h", max_width=250),
            icon=folium.Icon(color=cor_do_veiculo(v, dentro), icon="truck", prefix="fa"),
        ).add_to(mapa)
    return mapa


st.set_page_config(page_title="GeoLog", page_icon="🚚", layout="wide")
st.title("🚚 GeoLog — Telemetria Logística e Persistência Poliglota")
st.caption("SQLite: motoristas e veículos (dados cadastrais)  |  MongoDB: telemetria GPS em GeoJSON com índice 2dsphere")

try:
    conn = iniciar_sqlite()
    colecao = iniciar_mongodb()
    colecao.database.client.admin.command("ping")
except Exception as erro:
    st.error(f"Não foi possível conectar aos bancos de dados: {erro}")
    st.stop()

with st.sidebar:
    st.header("🔎 Busca por Raio")
    nome_ponto = st.selectbox("Ponto de referência", list(PONTOS_DE_APOIO) + ["Coordenada personalizada"])
    if nome_ponto == "Coordenada personalizada":
        ref_lat = st.number_input("Latitude", value=-7.1195, format="%.4f")
        ref_lon = st.number_input("Longitude", value=-34.8800, format="%.4f")
    else:
        ref_lat, ref_lon = PONTOS_DE_APOIO[nome_ponto]
    raio_km = st.slider("Raio de busca (km)", min_value=1, max_value=20, value=6)
    st.divider()
    st.header("🛰️ Simulador (Bônus)")
    if st.button("Simular Movimentação", type="primary", width="stretch"):
        st.session_state["simulados"] = simular_movimentacao(colecao, ultimas_leituras(colecao))
        st.rerun()
    if st.session_state.get("simulados"):
        st.success(f"{st.session_state['simulados']} novas posições GPS gravadas no MongoDB.")

cadastro = carregar_cadastro(conn)
ultimas = ultimas_leituras(colecao)
unificada = visao_unificada(cadastro, ultimas)
no_raio = veiculos_no_raio(colecao, ultimas, ref_lat, ref_lon, raio_km)
ids_no_raio = [d["veiculo_id"] for d in no_raio]
historico = historico_telemetria(colecao)

aba_mapa, aba_unificada, aba_dashboard = st.tabs(
    ["🗺️ Mapa e Busca por Raio", "🔗 Visão Unificada", "📊 Dashboard Analítico"])

with aba_mapa:
    st.subheader(f"Veículos a até {raio_km} km de: {nome_ponto}")
    col_mapa, col_lista = st.columns([3, 2])
    with col_mapa:
        mapa = montar_mapa(ref_lat, ref_lon, raio_km, nome_ponto, unificada, ids_no_raio, historico)
        st_folium(mapa, height=520, use_container_width=True, returned_objects=[], key="mapa")
        st.caption("🟢 dentro do raio  ⚪ fora do raio  🔴 alerta de velocidade (> 80 km/h)  — linhas: rota percorrida")
    with col_lista:
        st.metric("Veículos dentro do raio", f"{len(ids_no_raio)} de {len(unificada)}")
        if ids_no_raio:
            tabela = unificada.set_index("veiculo_id").loc[ids_no_raio].reset_index()
            tabela["distância (km)"] = tabela.apply(
                lambda v: round(distancia_km(ref_lat, ref_lon, v["latitude"], v["longitude"]), 2), axis=1)
            st.dataframe(tabela[["placa", "motorista", "distância (km)", "velocidade", "temperatura"]],
                         hide_index=True, width="stretch")
        else:
            st.info("Nenhum veículo dentro do raio selecionado.")

with aba_unificada:
    st.subheader("Join poliglota: cadastro (SQLite) + última telemetria (MongoDB)")
    tabela = unificada.copy()
    tabela["Coordenadas Atualizadas"] = tabela.apply(
        lambda v: f"{v['latitude']:.5f}, {v['longitude']:.5f}", axis=1)
    tabela = tabela.rename(columns={
        "motorista": "Nome do Motorista", "placa": "Placa",
        "temperatura": "Última Temperatura (°C)", "velocidade": "Velocidade (km/h)",
        "timestamp": "Última Leitura",
    })
    st.dataframe(tabela[["Nome do Motorista", "Placa", "Última Temperatura (°C)", "Velocidade (km/h)",
                         "Coordenadas Atualizadas", "Última Leitura"]], hide_index=True, width="stretch")

with aba_dashboard:
    ativos = int((unificada["status"] == "Ativo").sum())
    alertas = int((unificada["velocidade"] > LIMITE_VELOCIDADE).sum())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Frotas ativas", f"{ativos} de {len(unificada)}")
    k2.metric("Temperatura média da carga", f"{unificada['temperatura'].mean():.1f} °C")
    k3.metric("Alertas de velocidade (> 80 km/h)", alertas)
    k4.metric("Leituras de telemetria", len(historico))

    if alertas:
        placas = ", ".join(unificada.loc[unificada["velocidade"] > LIMITE_VELOCIDADE, "placa"])
        st.warning(f"⚠️ Acima de {LIMITE_VELOCIDADE} km/h: {placas}")

    g1, g2 = st.columns([2, 1])
    with g1:
        hist = historico.merge(cadastro[["veiculo_id", "placa"]], on="veiculo_id")
        fig = px.line(hist, x="timestamp", y="temperatura", color="placa", markers=True,
                      title="Histórico de temperatura por veículo",
                      labels={"timestamp": "Horário", "temperatura": "Temperatura (°C)", "placa": "Veículo"})
        st.plotly_chart(fig, width="stretch")
    with g2:
        status = cadastro["status"].value_counts().reset_index()
        status.columns = ["status", "quantidade"]
        fig = px.pie(status, names="status", values="quantidade", hole=0.4,
                     title="Status dos motoristas")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Métricas consolidadas (pipeline de agregação no MongoDB)")
    metricas = metricas_por_veiculo(colecao).merge(cadastro[["veiculo_id", "placa"]], on="veiculo_id")
    st.dataframe(metricas[["placa", "leituras", "temperatura_media", "temperatura_min", "temperatura_max",
                           "velocidade_max"]].round(1), hide_index=True, width="stretch")
