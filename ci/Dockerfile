FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y git docker.io && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git config --global --add safe.directory /repo
RUN git config --global pull.ff only

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["python", "app.py"]