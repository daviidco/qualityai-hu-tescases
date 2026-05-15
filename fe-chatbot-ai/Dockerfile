FROM python:3.11-slim

WORKDIR /app

COPY fe-chatbot-ai/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fe-chatbot-ai/ .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
