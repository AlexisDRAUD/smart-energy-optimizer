# Image unique du backend. Elle est lancee en plusieurs conteneurs, chacun avec
# une commande differente : migrate, api, collector, etl. Voir docker-compose.yml.
#
# Construite depuis la racine du depot, parce qu elle installe packages/features.
FROM python:3.12-slim

WORKDIR /app

COPY packages/features /opt/features
RUN pip install --no-cache-dir /opt/features

COPY services/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/backend .

EXPOSE 8080

CMD ["./scripts/start.sh"]
