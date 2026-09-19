FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY admin_service ./admin_service
COPY main.py .
EXPOSE 8100
CMD ["python", "main.py"]
