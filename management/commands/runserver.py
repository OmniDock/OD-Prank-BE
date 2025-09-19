import uvicorn
from dotenv import load_dotenv

def run():
    """Start the FastAPI development server"""
    load_dotenv(".env.local")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="debug"
    )

if __name__ == "__main__":
    run()