import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logging.Formatter.converter = time.gmtime

API_BASE_URL = "https://api.cartola.globo.com"
MERCADO_ENDPOINT = f"{API_BASE_URL}/atletas/mercado"
STATUS_MERCADO_ENDPOINT = f"{API_BASE_URL}/mercado/status"

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "cartola_fc_db")

COL_CLUBES = "clubes_rodada_atual"
COL_ATLETAS = "atletas_rodada_atual"
COL_MERCADO = "mercado_rodada_atual"


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def conectar_mongodb() -> MongoClient:
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        db = client[MONGO_DB_NAME]
        logging.info("Conectado ao MongoDB com sucesso.")
        return db
    except Exception as e:
        logging.exception("Falha ao conectar no MongoDB: %s", e)
        raise


def buscar_dados_mercado(session: Optional[requests.Session] = None,
                         url: str = MERCADO_ENDPOINT) -> Dict[str, Any]:
    sess = session or requests.Session()
    headers = {
        "Accept": "application/json",
        "User-Agent": "cartola-etl/1.0 (+https://example.internal)",
    }

    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = sess.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            logging.info("Dados obtidos de %s (tentativa %d).", url, tentativa)
            return resp.json()
        except requests.RequestException as e:
            logging.warning("Erro na requisição (tentativa %d/%d): %s", tentativa, max_tentativas, e)
            if tentativa == max_tentativas:
                logging.exception("Falha ao buscar %s após %d tentativas.", url, max_tentativas)
                raise
            time.sleep(2 ** tentativa)


def buscar_status_mercado() -> Dict[str, Any]:
    try:
        return buscar_dados_mercado(url=STATUS_MERCADO_ENDPOINT)
    except requests.RequestException:
        logging.warning("Não foi possível obter /mercado/status; seguindo sem ele.")
        return {}


def processar_e_gravar_dados(db, dados_mercado: Dict[str, Any],
                             status_mercado: Optional[Dict[str, Any]] = None) -> None:
    timestamp = iso_utc_now()

    clubes_obj = dados_mercado.get("clubes", {})
    if isinstance(clubes_obj, dict):
        ops: List[UpdateOne] = []
        for club_id_str, club_data in clubes_obj.items():
            try:
                club_id = int(club_id_str)
            except (TypeError, ValueError):
                club_id = club_data.get("id")
                if club_id is None:
                    logging.warning("Clube com ID inválido será ignorado: %s", club_data)
                    continue

            doc = {
                "_id": club_id,
                "nome": club_data.get("nome"),
                "abreviacao": club_data.get("abreviacao"),
                "escudos": club_data.get("escudos"),
                "nome_fantasia": club_data.get("nome_fantasia"),
                "timestamp_coleta": timestamp,
            }
            ops.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": doc},
                    upsert=True,
                )
            )

        if ops:
            try:
                result = db[COL_CLUBES].bulk_write(ops, ordered=False)
                upserts = (result.upserted_count or 0)
                modified = (result.modified_count or 0)
                logging.info("Clubes upsert: %d, modificados: %d.", upserts, modified)
            except PyMongoError as e:
                logging.exception("Erro ao gravar clubes: %s", e)
                raise
    else:
        logging.warning("Campo 'clubes' não está no formato esperado (dict).")


    atletas_list = dados_mercado.get("atletas", [])
    if not isinstance(atletas_list, list):
        logging.warning("Campo 'atletas' não é uma lista. Valor: %s", type(atletas_list))
        atletas_list = []

    for atleta in atletas_list:
        atleta["timestamp_coleta"] = timestamp

    try:
        delete_res = db[COL_ATLETAS].delete_many({})
        logging.info("Removidos %d documentos antigos de atletas.", delete_res.deleted_count)
        if atletas_list:
            db[COL_ATLETAS].insert_many(atletas_list, ordered=False)
            logging.info("Inseridos %d atletas.", len(atletas_list))
        else:
            logging.info("Nenhum atleta para inserir.")
    except PyMongoError as e:
        logging.exception("Erro ao gravar atletas: %s", e)
        raise


    fonte = status_mercado or dados_mercado
    mercado_doc = {
        "rodada_atual": fonte.get("rodada_atual"),
        "status_mercado": fonte.get("status_mercado"),
        "aviso": fonte.get("aviso"),
        "fechamento": fonte.get("fechamento"),
        "timestamp_coleta": timestamp,
    }
    if mercado_doc["rodada_atual"] is None:
        logging.warning("Status do mercado veio sem 'rodada_atual' (campos podem ficar nulos).")

    try:
        db[COL_MERCADO].delete_many({})
        db[COL_MERCADO].insert_one(mercado_doc)
        logging.info("Status do mercado gravado com sucesso.")
    except PyMongoError as e:
        logging.exception("Erro ao gravar status do mercado: %s", e)
        raise

def main() -> int:
    logging.info("Iniciando ETL Cartola FC...")
    try:
        db = conectar_mongodb()
        logging.info("Buscando dados na API do Cartola FC...")
        dados = buscar_dados_mercado()
        logging.info("Buscando status do mercado...")
        status = buscar_status_mercado()
        logging.info("Processando e gravando dados...")
        processar_e_gravar_dados(db, dados, status)
        logging.info("Finalizado com sucesso.")
        return 0
    except Exception as e:
        logging.error("Execução encerrada com erro: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
