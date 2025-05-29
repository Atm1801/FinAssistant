# Use a Python 3.10 slim base image for a smaller footprint
FROM python:3.10-slim-buster

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies, including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    flac \
    # Add any other system dependencies if needed
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements.txt file first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . /app

# Ensure correct permissions for executable scripts
RUN chmod +x ./start_all_agents.sh

# Expose the ports your applications will run on
EXPOSE 8000 8001 8002 8003 8004 8005 8006 8501

# Command to run when the container starts
ENTRYPOINT ["./start_all_agents.sh"]
