FROM python:3.12-slim

WORKDIR /app 

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1

RUN useradd --create-home appuser
USER appuser 

CMD ["python", "worker.py"]