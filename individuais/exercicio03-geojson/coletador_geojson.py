import io
import os
import zipfile

import pandas as pd
import geopandas as gpd
import requests
from pymongo import MongoClient
from shapely.geometry import Point

URLS_DADOS = [
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/Unidades_Basicas_Saude-UBS_csv.zip",
    "https://s3-sa-east-1.amazonaws.com/ckan.saude.gov.br/UBS/ubs.csv",
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/PDA/UNIDADES_BASICAS_SAUDE/ubs.csv",
]
NOME_ARQUIVO = "ubs.csv"
MONGO_URI = "mongodb://localhost:27017/"
NOME_BANCO = "geodados"
NOME_COLECAO = "unidades_saude"


def baixar_dados():
    print("Baixando dados de UBS...")
    for url in URLS_DADOS:
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            conteudo = response.content
            if zipfile.is_zipfile(io.BytesIO(conteudo)):
                with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
                    nome_csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                    conteudo = z.read(nome_csv)
            with open(NOME_ARQUIVO, "wb") as f:
                f.write(conteudo)
            print(f"Dados baixados de {url}")
            return True
        except requests.RequestException:
            print(f"Não deu para baixar de {url}")

    if os.path.exists(NOME_ARQUIVO):
        print(f"Usando o arquivo {NOME_ARQUIVO} da pasta")
        return True

    print(f"Baixe o CSV de UBS pelo navegador e salve como {NOME_ARQUIVO} nesta pasta")
    return False


def processar_dados():
    print("Processando dados...")
    try:
        df = pd.read_csv(NOME_ARQUIVO, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(NOME_ARQUIVO, sep=None, engine="python", dtype=str, encoding="latin-1")

    df.columns = [c.strip().lower() for c in df.columns]
    col_lat = next(c for c in df.columns if "latitude" in c)
    col_lon = next(c for c in df.columns if "longitude" in c)

    df["latitude"] = pd.to_numeric(df.pop(col_lat).str.replace(",", "."), errors="coerce")
    df["longitude"] = pd.to_numeric(df.pop(col_lon).str.replace(",", "."), errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["latitude"].between(-34, 6) & df["longitude"].between(-74, -28)]

    geometry = [Point(xy) for xy in zip(df["longitude"], df["latitude"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4674")
    print(f"Dados processados: {len(gdf)} registros válidos")
    return gdf


def salvar_no_mongodb(gdf):
    print("Conectando ao MongoDB...")
    collection = MongoClient(MONGO_URI)[NOME_BANCO][NOME_COLECAO]
    collection.delete_many({})

    propriedades = gdf.drop(columns=["latitude", "longitude", "geometry"])
    propriedades = propriedades.astype(object).where(propriedades.notna(), None)

    features = []
    for (_, row), props in zip(gdf.iterrows(), propriedades.to_dict("records")):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": props,
        })

    collection.insert_many(features)
    print(f"Inseridos {len(features)} documentos no MongoDB")

    collection.create_index([("geometry", "2dsphere")])
    print("Índice geoespacial criado com sucesso")
    return collection


def consulta_exemplo(collection):
    print("\nUBS mais próximas do centro de João Pessoa:")
    perto = collection.find({
        "geometry": {"$near": {
            "$geometry": {"type": "Point", "coordinates": [-34.8800, -7.1200]},
            "$maxDistance": 3000,
        }}
    }).limit(5)
    for doc in perto:
        print(" -", doc["properties"].get("nome"), "|", doc["properties"].get("bairro"))


def main():
    if not baixar_dados():
        return
    gdf = processar_dados()
    collection = salvar_no_mongodb(gdf)
    consulta_exemplo(collection)
    print(f"\nProcesso concluído! Dados em {NOME_BANCO}.{NOME_COLECAO}")


if __name__ == "__main__":
    main()
