import uvicorn
from .config import Settings

if __name__ == '__main__':
    settings = Settings()
    uvicorn.run('backend.api.main:app', host=settings.host, port=settings.port,
                workers=1, limit_concurrency=32, access_log=False)
