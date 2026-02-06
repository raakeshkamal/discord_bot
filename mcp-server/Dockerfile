FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install uv && uv pip install --system --no-cache -r requirements.txt

COPY server.py .
# Create data directory
RUN mkdir -p data

CMD ["python", "server.py"]
