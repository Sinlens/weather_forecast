# Setting the base image to use for the container
FROM python:3.11-slim

# Setting the working directory inside the container
WORKDIR /app

# Installing system dependencies for psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copying the requirements file to the working directory
COPY requirements.txt .

# Installing the dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copying the rest of the application code to the working directory
COPY . .

# Setting the command to run the application when the container starts
CMD ["python", "forecast.py", "--rate", "0.2"]