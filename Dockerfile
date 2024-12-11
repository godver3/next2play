# Use an official Python runtime as the base image
FROM python:3.9-slim

# Install Node.js
RUN apt-get update && apt-get install -y nodejs npm

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies with forced upgrade
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the current directory contents into the container at /app
COPY app.py /app/app.py
COPY templates/index.html /app/templates/index.html
COPY templates/login.html /app/templates/login.html
COPY static/js/index.js /app/static/js/index.js
COPY static/css/styles.css /app/static/css/styles.css
COPY templates/stats.html /app/templates/stats.html
#COPY hltbSearch.js /app/hltbSearch.js
COPY node_modules /app/node_modules

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Set environment variables with default values
ENV ADMIN_PASSWORD=admin123
ENV SECRET_KEY=default-secret-key

# Run app.py when the container launches
CMD ["python", "app.py"]
