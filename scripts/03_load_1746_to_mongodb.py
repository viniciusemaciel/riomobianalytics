#!/usr/bin/env python3
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
from tqdm import tqdm
import config
import os
import sys

def load_bairros_lookup():
    """Carrega o de-para id_bairro (codbnum) → nome do bairro.
    Retorna dict vazio se o arquivo não existir — loader segue sem quebrar."""
    path = config.BAIRROS_LOOKUP_FILE
    if not os.path.exists(path):
        print(f"Bairros lookup file not found at {path}; bairro will be empty")
        return {}
    df = pd.read_csv(path)
    return dict(zip(df['codbnum'].astype(int), df['nome'].astype(str).str.strip()))


class Reclamacoes1746Loader:
    def __init__(self):
        self.client = MongoClient(config.MONGO_URI)
        self.db = self.client[config.MONGO_DB]
        self.collection = self.db.reclamacoes_1746_raw
        self.bairros_lookup = load_bairros_lookup()

    def detect_csv_format(self, df):
        if 'protocolo' in df.columns:
            return 'reclamacoes'
        elif 'id_chamado' in df.columns:
            return 'chamados_v2'
        else:
            raise ValueError(f"Unknown CSV format. Columns: {df.columns.tolist()}")

    def map_chamados_v2(self, df):
        mapped_df = df.copy()

        rename_dict = {}
        for old_col, new_col in config.CHAMADOS_V2_COLUMN_MAPPING.items():
            if old_col in mapped_df.columns:
                rename_dict[old_col] = new_col

        mapped_df = mapped_df.rename(columns=rename_dict)

        # Derivar 'servico' a partir de 'tipo' via curadoria (TIPO_TO_SERVICO).
        # Tipos ausentes do mapa (Alvará, Estacionamento, etc.) são descartados
        # por serem irrelevantes para segurança de paradas.
        if 'tipo' in mapped_df.columns:
            mapped_df['tipo'] = mapped_df['tipo'].astype(str).str.strip()
            total_before = len(mapped_df)
            mapped_df = mapped_df[mapped_df['tipo'].isin(config.TIPO_TO_SERVICO.keys())].copy()
            dropped = total_before - len(mapped_df)
            print(f"Filtered out {dropped} records with irrelevant 'tipo' "
                  f"(kept {len(mapped_df)} relevant to bus stop safety)")
            mapped_df['servico'] = mapped_df['tipo'].map(config.TIPO_TO_SERVICO)

        # subtipo é mais informativo que qualquer descrição — usa como descricao
        if 'subtipo' in mapped_df.columns and 'descricao' not in mapped_df.columns:
            mapped_df['descricao'] = mapped_df['subtipo'].astype(str).str.strip()

        # Resolve nome do bairro a partir de id_bairro via lookup (Limite_de_Bairros).
        if 'id_bairro' in mapped_df.columns and self.bairros_lookup:
            id_int = pd.to_numeric(mapped_df['id_bairro'], errors='coerce').astype('Int64')
            mapped_bairros = id_int.map(self.bairros_lookup)

            nan_after_convert = id_int.isna().sum()
            missing_in_lookup = (id_int.notna() & mapped_bairros.isna()).sum()
            if nan_after_convert or missing_in_lookup:
                print(f"[warn] Bairros: {nan_after_convert} id_bairro inválidos (não-numéricos), "
                      f"{missing_in_lookup} não encontrados no lookup — ficarão vazios.")

            mapped_df['bairro'] = mapped_bairros.fillna('')
            resolved = (mapped_df['bairro'] != '').sum()
            print(f"Resolved bairro name for {resolved}/{len(mapped_df)} records")

        for col, default_value in config.CHAMADOS_V2_DEFAULTS.items():
            if col not in mapped_df.columns:
                mapped_df[col] = default_value

        required = ['protocolo', 'data_abertura', 'servico', 'latitude', 'longitude']
        missing = [col for col in required if col not in mapped_df.columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        null_coords = mapped_df[['latitude', 'longitude']].isnull().any(axis=1).sum()
        if null_coords > 0:
            print(f"Dropping {null_coords} records with null coordinates")
            mapped_df = mapped_df.dropna(subset=['latitude', 'longitude'])

        return mapped_df

    def normalize_categoria(self, servico):
        for categoria in config.CATEGORIA_PESOS.keys():
            if categoria.lower() in servico.lower():
                return categoria
        return 'Outros'

    def get_peso_categoria(self, categoria):
        return config.CATEGORIA_PESOS.get(categoria, 0.3)

    def normalize_criticidade(self, criticidade):
        if pd.isna(criticidade):
            return 'Baixa'

        crit = str(criticidade).strip().title()
        if crit in ['Alta', 'Média', 'Media', 'Baixa']:
            return crit
        return 'Baixa'

    def load_from_csv(self):
        df = pd.read_csv(config.RECLAMACOES_1746_FILE)
        print(f"Loading {len(df)} complaints...")

        csv_format = self.detect_csv_format(df)
        print(f"Format: {csv_format}")

        if csv_format == 'chamados_v2':
            df = self.map_chamados_v2(df)
        else:
            required_columns = ['protocolo', 'data_abertura', 'servico', 'latitude', 'longitude']
            missing = [col for col in required_columns if col not in df.columns]

            if missing:
                print(f"Missing columns: {missing}")
                print(f"Available: {df.columns.tolist()}")
                return False

        inserted_count = 0
        duplicates_count = 0
        errors_count = 0

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing"):
            try:
                if pd.notna(row['data_abertura']):
                    data_abertura = pd.to_datetime(row['data_abertura'])
                else:
                    data_abertura = datetime.now()

                categoria = self.normalize_categoria(row['servico'])
                peso = self.get_peso_categoria(categoria)
                criticidade = self.normalize_criticidade(
                    row.get('criticidade', 'Baixa')
                )

                doc = {
                    'protocolo': str(row['protocolo']),
                    'data_abertura': data_abertura,
                    'servico': categoria,
                    'descricao': str(row.get('descricao', '')),
                    'status': str(row.get('status', 'Aberto')),
                    'lat': float(row['latitude']),
                    'lon': float(row['longitude']),
                    'peso': peso,
                    'criticidade': criticidade,
                    'bairro': str(row.get('bairro', '')),
                    'synced_to_neo4j': False,
                    'imported_at': datetime.now()
                }

                # stop_id e distância já vêm pré-calculados no CSV novo — persistir
                # para o sync (04) usar direto em vez de refazer o spatial join.
                stop_id = row.get('stop_id_mais_proximo')
                if pd.notna(stop_id):
                    doc['stop_id_mais_proximo'] = str(stop_id)
                dist = row.get('distancia_metros')
                if pd.notna(dist):
                    doc['distancia_metros'] = float(dist)

                doc['localizacao'] = {
                    'type': 'Point',
                    'coordinates': [float(row['longitude']), float(row['latitude'])]
                }

                try:
                    self.collection.insert_one(doc)
                    inserted_count += 1
                except Exception as e:
                    if 'duplicate key' in str(e):
                        duplicates_count += 1
                    else:
                        errors_count += 1

            except Exception as e:
                errors_count += 1
                continue

        print(f"\nInserted: {inserted_count}")
        print(f"Duplicates: {duplicates_count}")
        print(f"Errors: {errors_count}")

        return True

    def create_summary(self):
        total = self.collection.count_documents({})
        print(f"\nTotal: {total} complaints")

        pipeline = [
            {'$group': {
                '_id': '$servico',
                'count': {'$sum': 1}
            }},
            {'$sort': {'count': -1}}
        ]

        print("By category:")
        for doc in self.collection.aggregate(pipeline):
            print(f"  {doc['_id']}: {doc['count']}")

        pipeline = [
            {'$group': {
                '_id': '$status',
                'count': {'$sum': 1}
            }}
        ]

        print("By status:")
        for doc in self.collection.aggregate(pipeline):
            print(f"  {doc['_id']}: {doc['count']}")

    def close(self):
        self.client.close()

    def run(self):
        print("1746 Complaint Loader\n")

        try:
            success = self.load_from_csv()
            if success:
                self.create_summary()
                print("\nComplaints loaded successfully")
                return True
            return False

        except Exception as e:
            print(f"\nLoad failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.close()


if __name__ == "__main__":
    loader = Reclamacoes1746Loader()
    success = loader.run()
    sys.exit(0 if success else 1)
