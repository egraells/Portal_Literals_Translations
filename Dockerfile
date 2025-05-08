# pull official base image
FROM python:3.11.12-slim

# set work directory: foler inside the container for the app code
WORKDIR /usr/src/app

# Set environment variables: 
# Prevents Python from writing pyc files to disc and 
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# copy from the root of the project to the work directory in the container
COPY . .