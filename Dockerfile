FROM python:3.12-slim

WORKDIR /app

# Dependências de sistema pra compilar xgboost e scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala as libs Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Variáveis de ambiente padrão (sobrescrevíveis no compose)
ENV PYTHONPATH=/app
ENV MONGO_URI=mongodb://admin:riomobianalytics2024@mongodb:27017/
ENV NEO4J_URI=bolt://neo4j:7687
ENV NEO4J_USER=neo4j
ENV NEO4J_PASSWORD=riomobianalytics2024

# Porta do Streamlit
EXPOSE 8501

ENTRYPOINT ["./docker-entrypoint.sh"]
