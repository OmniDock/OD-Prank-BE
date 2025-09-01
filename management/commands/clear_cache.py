import asyncio
import sys
from pathlib import Path

def run():
    """Clear the Redis cache"""
    
    # Add the project root to Python path so we can import the app
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        from app.services.cache_service import CacheService
        
        async def clear_cache():
            cache = await CacheService.get_global()
            await cache.clear_all()
            print("Cache cleared successfully")
        
        asyncio.run(clear_cache())
        
    except ImportError as e:
        print(f"Error importing CacheService: {e}")
        print("Make sure you're running this from the project root directory.")
    except Exception as e:
        print(f"Error clearing cache: {e}")

if __name__ == "__main__":
    run()