# Image separee du backend : dependances lourdes (lightgbm, scikit-learn, mlflow)
# et cycle de vie different, lancee a la demande et pas en continu.
#
# Le ML lit la base en SQL direct et n ecrit rien dedans. Il n importe donc pas
# les modeles du backend, seulement packages/features, pour que l entrainement et
# le service calculent les variables de la meme facon.
FROM python:3.12-slim

WORKDIR /app

COPY packages/features /opt/features
RUN pip install --no-cache-dir /opt/features

COPY services/ml/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ml .

# Entrypoint: start MLflow server and run a training job on the bundled CSV
COPY services/ml/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
