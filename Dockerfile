FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "python -m streamlit run src/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"]
