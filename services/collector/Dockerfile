FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app:/app/packages/common/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

CMD ["python", "-m", "collector.main"]
