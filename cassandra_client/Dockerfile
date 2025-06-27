# Use the official Python image as a base
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY simpleClient.py ./

# Set the default command to run the application
CMD ["python3", "simpleClient.py"]