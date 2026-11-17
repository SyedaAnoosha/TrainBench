"""TrainBench application server starter."""
import uvicorn
from backend.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
