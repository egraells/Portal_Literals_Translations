# pull official base image
FROM python:3.11.12-slim AS builder

# Create the app directory
RUN mkdir /app

# set work directory: foler inside the container for the app code
WORKDIR /app

# Set environment variables: 
# Prevents Python from writing pyc files to disc and 
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Install dependencies first for caching benefit
RUN pip install --upgrade pip 
COPY requirements.txt /app/ 
RUN pip install --no-cache-dir -r requirements.txt

# copy from the root of the project to the work directory in the container
# COPY . .

# Stage 2: Production stage
FROM python:3.11.12-slim
 
# Create a non-root user
# This is a best practice for security reasons
RUN useradd -m -r appuser && \
   mkdir /app && \
   chown -R appuser /app
 
# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
 
# Set the working directory
WORKDIR /app
 
# Copy application code, except for files in .dockerignore and 
# assign the user and group ownership to the non-root user
COPY --chown=appuser:appuser . .

# Create the folders for saving translations and review requests
RUN mkdir /app/media && chmod 755 /app/media && chown appuser:appuser /app/media
RUN mkdir /app/media/review_requests && chmod 755 /app/media/review_requests && chown appuser:appuser /app/media/review_requests
RUN mkdir /app/media/translation_requests && chmod 755 /app/media/translation_requests && chown appuser:appuser /app/media/translation_requests

 
# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
 
# Switch to non-root user
USER appuser
 
# Expose the application port
EXPOSE 8000 
# for debugging 
EXPOSE 5678 

# Make entry file executable
RUN chmod +x  /app/entrypoint.prod.sh
 
# Start the application using Gunicorn
CMD ["/app/entrypoint.prod.sh"]