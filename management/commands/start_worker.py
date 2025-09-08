import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv


def run():
    """Start a Celery worker for local development.

    Usage:
      python manage.py start_worker

    Environment variables (optional):
      - REDIS_URL (default: redis://localhost:6379)
      - CELERY_CONCURRENCY (default: 2)
      - ELEVENLABS_MAX_CONCURRENCY (default: 2)
    """

    # Ensure .env.local is loaded
    load_dotenv(".env.local")

    # Defaults for local dev
    env = os.environ.copy()
    env.setdefault("REDIS_URL", "redis://localhost:6379")
    env.setdefault("ELEVENLABS_MAX_CONCURRENCY", "5")

    concurrency = env.get("CELERY_CONCURRENCY", "5")

    # Use uv to run celery so it uses the project's virtual env from pyproject
    cmd = [
        "uv", "run", "celery",
        "-A", "app.celery.config.celery_app",
        "worker",
        "--loglevel=INFO",
        f"--concurrency={concurrency}",
        "--prefetch-multiplier=1",
    ]

    print("Starting Celery worker with command:\n ", " ".join(cmd))
    print(f"REDIS_URL={env['REDIS_URL']}  ELEVENLABS_MAX_CONCURRENCY={env['ELEVENLABS_MAX_CONCURRENCY']}  CELERY_CONCURRENCY={concurrency}")

    # Execute attached to the current terminal
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Celery worker exited with error: {e}")


if __name__ == "__main__":
    run()


