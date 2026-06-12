import os
import urllib.parse

class Settings:
    PROJECT_NAME: str = "Enterprise Fraud Detection Pipeline API"
    
    # Database Settings (MySQL)
    # Default to localhost pricing_system database
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "K@shish@2005")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "pricing_system")
    
    @property
    def DATABASE_URL(self) -> str:
        escaped_password = urllib.parse.quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+pymysql://{self.MYSQL_USER}:{escaped_password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    # Redis Settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # JWT Authentication Settings
    # Standard security key (change in production)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "b39ad27f3538ace3f22ed0439fca09485236d35452dfc5db")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Fraud System Thresholds
    ALERT_THRESHOLD: int = 75  # Alert generated if combined risk score >= 75

settings = Settings()
