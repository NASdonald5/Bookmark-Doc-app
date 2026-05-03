FROM python:3.9-slim
WORKDIR /app
# This line installs both required libraries
RUN pip install --no-cache-dir flask beautifulsoup4 json
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
