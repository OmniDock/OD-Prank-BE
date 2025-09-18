import asyncio
import json
import sys
import uuid
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client
from app.core.config import settings
from app.core.auth import get_current_user, AuthUser
from app.repositories.scenario_repository import ScenarioRepository
from app.models.scenario import Scenario
from app.models.voice_line import VoiceLine

def run():
    """Upload a scenario JSON file to the database"""
    
    # Create synchronous database engine and session
    database_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db_session:

        # Get the JSON file path from command line arguments
        if len(sys.argv) < 3:
            print("Usage: python manage.py upload <path_to_json_file>")
            print("Example: python manage.py upload management/scenarios/kleber_scenario.json")
            print("Note: Requires email and password to be set")
            return
        
        json_file_path = sys.argv[2]
        
        # Get current authenticated user using Supabase login
        import os
        
        # Get credentials from environment
        email = ''
        password = ''
        
        if not email or not password:
            print("Error: email and password environment variables not set")
            return
        
        try:
            # Create Supabase client
            supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
            
            # Login with email/password
            print(f"Logging in with email: {email}")
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user:
                print("Error: Login failed")
                return
                
            user_id = auth_response.user.id
            user_email = auth_response.user.email
            print(f"Successfully logged in as: {user_email} (ID: {user_id})")
            
        except Exception as e:
            print(f"Error logging in: {e}")
            return
        
        # Check if file exists
        if not Path(json_file_path).exists():
            print(f"Error: File '{json_file_path}' not found")
            return
        
        # Read and parse JSON file
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
            
            print(f"Successfully loaded JSON file: {json_file_path}")
            print(f"Data type: {type(scenarios_data)}")
            print(f"Number of scenarios: {len(scenarios_data) if isinstance(scenarios_data, list) else 'Not a list'}")
            
            # Print the first scenario structure for debugging
            if isinstance(scenarios_data, list) and len(scenarios_data) > 0:
                print("\nFirst scenario structure:")
                first_scenario = scenarios_data[0]
                print(f"Title: {first_scenario.get('title', 'N/A')}")
                print(f"Language: {first_scenario.get('language', 'N/A')}")
                print(f"Voice lines count: {len(first_scenario.get('voice_lines', []))}")
                
                # Show first few voice lines
                voice_lines = first_scenario.get('voice_lines', [])
                if voice_lines:
                    print("\nFirst 3 voice lines:")
                    for i, vl in enumerate(voice_lines[:3]):
                        print(f"  {i+1}. Type: {vl.get('type', 'N/A')}, Text: {vl.get('text', 'N/A')[:50]}...")
            
            # Use the injected database session
            print("\nUsing injected database session...")
            
            # Extract voice_lines from the dict
            voice_lines_data = first_scenario.pop('voice_lines', [])
            
            # Add the user_id
            first_scenario['user_id'] = user_id
            
            # Create the scenario without voice_lines
            scenario = Scenario(**first_scenario)
            db_session.add(scenario)
            db_session.flush()  # Get the scenario ID
            
            print(f"Created scenario with ID: {scenario.id}")
            
            # Create voice_lines separately
            for vl_data in voice_lines_data:
                vl_data['scenario_id'] = scenario.id
                voice_line = VoiceLine(**vl_data)
                db_session.add(voice_line)
            
            print(f"Created {len(voice_lines_data)} voice lines")
            
            # Commit
            db_session.commit()
            print("Successfully uploaded scenario to database!")

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file: {e}")
            return
        except Exception as e:
            print(f"Error reading file: {e}")
            return




if __name__ == "__main__":
    run()
