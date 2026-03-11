FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y git curl ca-certificates && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] \
    https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*



RUN git config --global --add safe.directory /repo
RUN git config --global pull.ff only

WORKDIR /app

COPY ci/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ci/app.py .
COPY ci/auth.py .
COPY ci/templates/ templates/

EXPOSE 8085

CMD ["python", "app.py"]