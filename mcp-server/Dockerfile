FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install uv && uv pip install --system --no-cache -r requirements.txt

COPY server.py .
# Create data directory and copy curriculum
RUN mkdir -p data
COPY data/rust_curriculum.json data/

CMD ["python", "server.py"]
