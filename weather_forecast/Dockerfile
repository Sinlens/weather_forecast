#setting the base image to use for the container
from python:3.11-slim
#setting the working directory inside the container
WORKDIR /app
#copying the requirements file to the working directory
COPY requirements.txt .
#installing the dependencies from the requirements file
run pip install --no-cache-dir -r requirements.txt

#copying the rest of the application code to the working directory
COPY . .
#setting the command to run the application when the container starts
CMD ["python", "forecast.py"]
