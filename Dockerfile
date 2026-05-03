FROM python:3.9-slim
WORKDIR /app
# This line is critical to install Flask
RUN pip install --no-cache-dir flask
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]

