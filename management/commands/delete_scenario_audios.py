import asyncio
import sys
from pathlib import Path


def run():
    """Delete all generated audios for a scenario and clear preferred voice.

    Usage:
        python manage.py delete_scenario_audios <scenario_id>
    """

    # Add the project root to Python path so we can import the app
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    if len(sys.argv) < 3:
        print("Usage: python manage.py delete_scenario_audios <scenario_id>")
        return

    try:
        scenario_id = int(sys.argv[2])
    except ValueError:
        print("Error: scenario_id must be an integer")
        return

    async def _delete():
        from sqlalchemy import select, delete
        from app.core.database import get_db_session
        from app.models.scenario import Scenario
        from app.models.voice_line import VoiceLine
        from app.models.voice_line_audio import VoiceLineAudio
        from app.services.tts_service import TTSService

        deleted_files = 0
        total_audio_rows = 0

        async for db in get_db_session():
            try:
                # Verify scenario exists
                scenario = await db.get(Scenario, scenario_id)
                if not scenario:
                    print(f"Scenario {scenario_id} not found")
                    break

                # Collect all voice line IDs for this scenario
                vl_result = await db.execute(
                    select(VoiceLine.id).where(VoiceLine.scenario_id == scenario_id)
                )
                voice_line_ids = [r[0] for r in vl_result.all()]

                if not voice_line_ids:
                    # Still clear preferred voice
                    scenario.preferred_voice_id = None
                    await db.commit()
                    print("No voice lines found. Cleared preferred_voice_id.")
                    break

                # Fetch all audio rows and storage paths
                rows_result = await db.execute(
                    select(VoiceLineAudio.id, VoiceLineAudio.storage_path)
                    .where(VoiceLineAudio.voice_line_id.in_(voice_line_ids))
                )
                rows = rows_result.all()
                total_audio_rows = len(rows)

                # Delete files from storage (best-effort)
                tts = TTSService()
                for _, storage_path in rows:
                    if storage_path:
                        ok = await tts.delete_audio_file(storage_path)
                        if ok:
                            deleted_files += 1

                # Delete audio rows from DB
                await db.execute(
                    delete(VoiceLineAudio).where(VoiceLineAudio.voice_line_id.in_(voice_line_ids))
                )

                # Clear scenario preferred voice
                scenario.preferred_voice_id = None

                await db.commit()

                print(
                    f"Scenario {scenario_id}: deleted {total_audio_rows} audio rows, "
                    f"removed {deleted_files} files, cleared preferred_voice_id."
                )
            except Exception as e:
                await db.rollback()
                print(f"Error deleting audios for scenario {scenario_id}: {e}")
            finally:
                await db.close()
                break

    asyncio.run(_delete())


if __name__ == "__main__":
    run()


