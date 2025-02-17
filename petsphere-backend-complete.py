# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
pydantic[email]==2.4.2
alembic==1.12.1
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
celery==5.3.4
redis==5.0.1
stripe==7.6.0
firebase-admin==6.2.0
python-dotenv==1.0.0
requests==2.31.0
gunicorn==21.2.0
pytest==7.4.3
httpx==0.25.1
tenacity==8.2.3
prometheus-client==0.18.0

# app/core/config.py
from pydantic import BaseSettings, PostgresDsn, validator, SecretStr
from typing import List, Optional, Dict, Any
import json
import os
from tenacity import retry, stop_after_attempt, wait_exponential

class Settings(BaseSettings):
    PROJECT_NAME: str = "PetSphere"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None
    SQLALCHEMY_POOL_SIZE: int = 5
    SQLALCHEMY_MAX_OVERFLOW: int = 10
    SQLALCHEMY_POOL_TIMEOUT: int = 30

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 5_242_880  # 5MB
    ALLOWED_FILE_TYPES: List[str] = ["image/jpeg", "image/png", "application/pdf"]
    
    # External Services
    STRIPE_SECRET_KEY: SecretStr
    STRIPE_WEBHOOK_SECRET: SecretStr
    FIREBASE_CREDENTIALS: Dict[str, Any]
    OPENAI_API_KEY: SecretStr

    class Config:
        env_file = ".env"
        case_sensitive = True

# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import Settings
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)
settings = Settings()

engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_size=settings.SQLALCHEMY_POOL_SIZE,
    max_overflow=settings.SQLALCHEMY_MAX_OVERFLOW,
    pool_timeout=settings.SQLALCHEMY_POOL_TIMEOUT,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error: {str(e)}")
        raise
    finally:
        db.close()

# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.db.session import get_db
from app.core.security import verify_token
from app.models.user import User
import time
from typing import Generator, Optional
import redis

settings = Settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

# Rate limiting setup
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def check_rate_limit(user_id: int) -> bool:
    current = int(time.time())
    key = f"rate_limit:{user_id}:{current // 60}"
    
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 90)  # Set expiry to 90 seconds
    result = pipe.execute()
    
    return result[0] <= settings.RATE_LIMIT_PER_MINUTE

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = verify_token(token)
        user = db.query(User).filter(User.id == payload["sub"]).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        if not check_rate_limit(user.id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
            
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

# app/api/v1/endpoints/pets.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import aiofiles
import hashlib
import os
from app.schemas.pet import PetCreate, PetUpdate, Pet, PetResponse
from app.crud.pet import pet_crud
from app.api.deps import get_current_user
from app.core.security import verify_token

router = APIRouter()

async def validate_file(file: UploadFile) -> None:
    if file.content_type not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {settings.ALLOWED_FILE_TYPES}"
        )
    
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
        )
    
    await file.seek(0)
    return content

@router.post("/pets/", response_model=PetResponse)
async def create_pet(
    pet: PetCreate,
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PetResponse:
    try:
        if photo:
            content = await validate_file(photo)
            
            # Generate secure filename
            file_hash = hashlib.sha256(content).hexdigest()
            ext = os.path.splitext(photo.filename)[1]
            secure_filename = f"{file_hash}{ext}"
            
            # Save file
            upload_dir = "uploads/pets"
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, secure_filename)
            
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            pet.photo_url = f"/static/pets/{secure_filename}"
        
        db_pet = pet_crud.create(db, obj_in=pet, owner_id=current_user.id)
        return PetResponse.from_orm(db_pet)
        
    except Exception as e:
        logger.error(f"Error creating pet: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create pet"
        )

# docker-compose.yml
version: "3.8"

services:
  web:
    build: 
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    
  db:
    image: postgres:13-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
  
  redis:
    image: redis:6-alpine
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A app.worker worker -l info --concurrency=2
    depends_on:
      - redis
    env_file:
      - .env
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    restart: unless-stopped

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana
    depends_on:
      - prometheus
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'petsphere'
    static_configs:
      - targets: ['web:8000']