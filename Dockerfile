# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Prevent Python from writing .pyc files and ensure logs are sent to the console
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (needed for certain pandas/openpyxl operations)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .

# Copy requirements first to leverage Docker's cache layers
COPY requirements.txt .

# Install all Python dependencies from the file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Create the data directory for the SQLite database
RUN mkdir -p /app/data

# Expose the port Flask runs on
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
