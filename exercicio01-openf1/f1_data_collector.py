import os
import sys
import time

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

load_dotenv()

API_BASE_URL = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "openf1_data")
YEAR = int(os.getenv("YEAR", "2023"))
CIRCUIT = os.getenv("CIRCUIT", "Monza")
SESSION_NAME = os.getenv("SESSION_NAME", "Race")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

DATASETS = {
    "sessions": {"collection": "sessions", "unique_keys": ["session_key"]},
    "drivers": {"collection": "drivers", "unique_keys": ["session_key", "driver_number"]},
    "laps": {"collection": "laps", "unique_keys": ["session_key", "driver_number", "lap_number"]},
}


def get_database(uri: str = MONGO_URI, db_name: str = DB_NAME):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        print(f"[OK] Conectado ao MongoDB - banco '{db_name}'")
        return client[db_name]
    except PyMongoError as e:
        print(f"[ERRO] Não foi possível conectar ao MongoDB: {e}")
        sys.exit(1)


def fetch_data(endpoint: str, params: dict) -> list:
    url = f"{API_BASE_URL}/{endpoint}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

            if response.status_code == 429 or response.status_code >= 500:
                wait = 2 ** attempt
                print(f"[AVISO] {endpoint}: HTTP {response.status_code}, "
                      f"tentativa {attempt}/{MAX_RETRIES}, aguardando {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                data = [data]

            print(f"[OK] {endpoint}: {len(data)} registro(s) recebido(s)")
            return data

        except requests.exceptions.Timeout:
            print(f"[AVISO] {endpoint}: timeout (tentativa {attempt}/{MAX_RETRIES})")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            print(f"[ERRO] Falha na requisição a {url}: {e}")
            return []
        except ValueError:
            print(f"[ERRO] Resposta de {url} não é um JSON válido")
            return []

    print(f"[ERRO] {endpoint}: desistindo após {MAX_RETRIES} tentativas")
    return []


def ensure_unique_index(collection, unique_keys: list) -> None:
    collection.create_index([(key, ASCENDING) for key in unique_keys], unique=True)


def save_to_collection(db, data: list, collection_name: str, unique_keys: list) -> None:
    if not data:
        print(f"[AVISO] Nada para salvar em '{collection_name}'")
        return

    collection = db[collection_name]
    inserted = updated = skipped = 0

    try:
        ensure_unique_index(collection, unique_keys)

        for doc in data:
            if any(doc.get(key) is None for key in unique_keys):
                skipped += 1
                continue

            filtro = {key: doc[key] for key in unique_keys}
            result = collection.update_one(filtro, {"$set": doc}, upsert=True)

            if result.upserted_id is not None:
                inserted += 1
            else:
                updated += 1

        print(f"[OK] '{collection_name}': {inserted} inserido(s), "
              f"{updated} atualizado(s), {skipped} ignorado(s)")

    except PyMongoError as e:
        print(f"[ERRO] Falha ao salvar em '{collection_name}': {e}")


def _cfg(endpoint: str) -> dict:
    return {"collection_name": DATASETS[endpoint]["collection"],
            "unique_keys": DATASETS[endpoint]["unique_keys"]}


def main() -> None:
    print(f"=== Coletor OpenF1 -> MongoDB | {SESSION_NAME} {CIRCUIT} {YEAR} ===")
    db = get_database()

    corrida = fetch_data("sessions", {"year": YEAR, "circuit_short_name": CIRCUIT, "session_name": SESSION_NAME})
    if not corrida:
        print("[ERRO] Corrida não encontrada na API. Confira YEAR, CIRCUIT e SESSION_NAME.")
        return
    session_key = corrida[0]["session_key"]
    meeting_key = corrida[0]["meeting_key"]
    print(f"[OK] Corrida encontrada: session_key={session_key}, meeting_key={meeting_key}")

    sessions = fetch_data("sessions", {"meeting_key": meeting_key})
    save_to_collection(db, sessions, **_cfg("sessions"))

    drivers = fetch_data("drivers", {"session_key": session_key})
    save_to_collection(db, drivers, **_cfg("drivers"))

    laps = fetch_data("laps", {"session_key": session_key})
    save_to_collection(db, laps, **_cfg("laps"))

    print("=== Coleta finalizada ===")


if __name__ == "__main__":
    main()
