import sys
import os
from pathlib import Path

def run():
    """Display all URL patterns in the FastAPI application"""
    
    # Add the project root to Python path so we can import the app
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        from app.main import app
        
        print("FastAPI URL Patterns:")
        print("=" * 50)
        
        # Get all routes from the FastAPI app
        routes = []
        
        def collect_routes(router, prefix=""):
            """Recursively collect routes from FastAPI router"""
            for route in router.routes:
                if hasattr(route, 'methods'):
                    # This is an API route
                    methods = sorted([method for method in route.methods if method != 'HEAD'])
                    path = prefix + route.path
                    name = getattr(route, 'name', 'unnamed')
                    endpoint = route.endpoint.__name__ if route.endpoint else 'unknown'
                    
                    routes.append({
                        'path': path,
                        'methods': methods,
                        'name': name,
                        'endpoint': endpoint
                    })
                elif hasattr(route, 'routes'):
                    # This is a sub-router (like APIRouter)
                    sub_prefix = prefix + getattr(route, 'prefix', '')
                    collect_routes(route, sub_prefix)
        
        # Collect all routes
        collect_routes(app)
        
        # Sort routes by path
        routes.sort(key=lambda x: x['path'])
        
        # Display routes in a formatted table
        if routes:
            # Calculate column widths
            max_path_width = max(len(route['path']) for route in routes)
            max_methods_width = max(len(', '.join(route['methods'])) for route in routes)
            max_name_width = max(len(route['name']) for route in routes)
            
            # Ensure minimum widths
            max_path_width = max(max_path_width, 10)
            max_methods_width = max(max_methods_width, 7)
            max_name_width = max(max_name_width, 10)
            
            # Print header
            header = f"{'Path':<{max_path_width}} | {'Methods':<{max_methods_width}} | {'Name':<{max_name_width}} | Endpoint"
            print(header)
            print("-" * len(header))
            
            # Print routes
            for route in routes:
                methods_str = ', '.join(route['methods'])
                print(f"{route['path']:<{max_path_width}} | {methods_str:<{max_methods_width}} | {route['name']:<{max_name_width}} | {route['endpoint']}")
            
            print(f"\nTotal routes: {len(routes)}")
        else:
            print("No routes found.")
            
    except ImportError as e:
        print(f"Error importing FastAPI app: {e}")
        print("Make sure you're running this from the project root directory.")
    except Exception as e:
        print(f"Error collecting routes: {e}")

if __name__ == "__main__":
    run()
