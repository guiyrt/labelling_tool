from pathlib import Path

def get_video_filepath(session_path: Path):
    session_id = session_path.name
    return session_path / "videoRecordings" / f"{session_id}_screenrecording.mkv"

def get_video_metadata_filepath(session_path: Path):
    session_id = session_path.name
    return session_path / "videoRecordings" / f"{session_id}_screenrecording_metadata.json"

def get_parquet_filepath(session_path: Path):
    session_id = session_path.name
    return session_path / "asd_events" / f"{session_id}_track_screen_position.parquet"

def get_gaze_parquet_filepath(session_path: Path):
    session_id = session_path.name
    return session_path / "ET" / f"{session_id}_eye_tracker.parquet"