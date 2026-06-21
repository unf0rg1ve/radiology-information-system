# Инструкция по деплою RIS MVP

## Вариант 1: Docker Compose (рекомендуется для production)

### Требования
- Docker 24+
- Docker Compose 2.20+
- 4 GB RAM минимум
- 20 GB свободного места

### Шаги

```bash
# 1. Клонировать репозиторий
git clone <repository-url>
cd ris-mvp

# 2. Запустить все сервисы
docker-compose up -d

# 3. Дождаться запуска (около 30 секунд)
docker-compose logs -f backend

# 4. Загрузить справочные данные
docker-compose exec backend python scripts/seed_refs.py

# 5. Проверить статус
curl http://localhost:8000/health
```

### Доступ после деплоя

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Orthanc DICOM | http://localhost:8042 |
| PostgreSQL | localhost:5432 (ris/ris) |

### Остановка
```bash
docker-compose down        # Остановить
docker-compose down -v     # Остановить и удалить данные
```

---

## Вариант 2: Ручная установка (для разработки)

### 2.1. Системные требования
- Ubuntu 22.04 / CentOS 8 / macOS 14+
- Python 3.12
- Node.js 22
- PostgreSQL 16
- Orthanc 1.12 (или Docker)

### 2.2. Установка PostgreSQL

```bash
# Ubuntu
sudo apt update
sudo apt install postgresql-16 postgresql-contrib

# Создать базу
sudo -u postgres psql -c "CREATE USER ris WITH PASSWORD 'ris';"
sudo -u postgres psql -c "CREATE DATABASE ris OWNER ris;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ris TO ris;"
```

### 2.3. Установка Orthanc (опционально, если не через Docker)

```bash
# Docker
sudo docker run -d --name orthanc \
  -p 8042:8042 -p 4242:4242 \
  -e ORTHANC__REGISTERED_USERS='{"orthanc": "orthanc"}' \
  jodogne/orthanc:1.12.3
```

### 2.4. Backend

```bash
cd backend

# Создать virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Создать .env файл
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://ris:ris@localhost:5432/ris
ORTHANC_URL=http://localhost:8042
ORTHANC_USER=orthanc
ORTHANC_PASSWORD=orthanc
SECRET_KEY=$(openssl rand -hex 32)
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=["https://your-domain.com"]
EOF

# Запустить миграции
alembic upgrade head

# Загрузить справочники
python scripts/seed_refs.py

# Запустить (development)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Запустить (production)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2.5. Frontend

```bash
cd frontend

# Установить зависимости
npm install

# Создать .env файл
cat > .env << EOF
VITE_API_URL=http://localhost:8000
EOF

# Собрать для production
npm run build

# Статический сервер (через nginx или serve)
sudo apt install nginx
sudo cp -r dist/* /var/www/html/
sudo cp nginx.conf /etc/nginx/sites-available/ris
sudo ln -s /etc/nginx/sites-available/ris /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

---

## Вариант 3: Облачный деплой (AWS/GCP)

### AWS ECS
```bash
# 1. Собрать Docker образы
docker-compose -f docker-compose.yml build

# 2. Push в ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

# 3. Деплой через ECS
aws ecs update-service --cluster ris-cluster --service ris-service --force-new-deployment
```

### GCP Cloud Run
```bash
# 1. Собрать
gcloud builds submit --tag gcr.io/PROJECT/ris-backend

# 2. Деплой
gcloud run deploy ris-backend \
  --image gcr.io/PROJECT/ris-backend \
  --platform managed \
  --region us-central1 \
  --set-env-vars DATABASE_URL=postgresql+asyncpg://...
```

---

## SSL/TLS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ris.your-domain.kz
```

---

## Мониторинг

### Health checks
```bash
curl http://localhost:8000/health
```

### PostgreSQL
```bash
sudo -u postgres psql -c "SELECT COUNT(*) FROM patients;"
```

### Orthanc
```bash
curl http://localhost:8042/system -u orthanc:orthanc
```

### Docker
```bash
docker-compose ps
docker-compose logs -f --tail=100
```

---

## Резервное копирование

### Автоматическое (cron)
```bash
# Ежедневный дамп
0 2 * * * pg_dump -h localhost -U ris -d ris | gzip > /backup/ris-$(date +\%Y\%m\%d).sql.gz

# DICOM backup
0 3 * * * tar -czf /backup/orthanc-$(date +\%Y\%m\%d).tar.gz /var/lib/orthanc/db
```

### Восстановление
```bash
gunzip < ris-20240115.sql.gz | psql -h localhost -U ris -d ris
```
