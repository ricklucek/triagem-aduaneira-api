FROM python:3.11-slim
WORKDIR /app
EXPOSE 5801
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade setuptools

COPY . .
CMD ["gunicorn","--workers", "6", "--bind", "0.0.0.0:8080","--timeout", "600", "wsgi:app"]