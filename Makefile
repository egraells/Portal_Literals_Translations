# Makefile for managing Docker dev and prod environments in *unix boxes

APP_NAME = ai-translator

# 🔁 Development (with override and code reloading)
dev:
	docker-compose up --build

# 🔒 Production (no override, built for deployment)
prod:
	docker-compose -f docker-compose.yml up --build -d

# 🧹 Clean up all containers and volumes
clean:
	docker-compose down --volumes --remove-orphans
	docker system prune -af

# 🔍 Access the container
shell:
	docker exec -it $(APP_NAME)-web-1 bash

# 📝 Tail logs
logs:
	docker-compose logs -f
