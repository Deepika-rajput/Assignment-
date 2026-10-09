import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")
        self.storage_dir = os.getenv("STORAGE_DIR", "storage")
        self.max_recipients_per_job = int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000"))


settings = Settings()
