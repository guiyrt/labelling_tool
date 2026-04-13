from pathlib import Path

def get_video_filepath(session_path: Path):
	session_id = session_path.name
	return session_path / "videoRecordings" / f"{session_id}_screen_recording.mkv"

def get_video_metadata_filepath(session_path: Path):
	session_id = session_path.name
	return session_path / "videoRecordings" / f"{session_id}_screen_recording_metadata.json"

def get_parquet_filepath(session_path: Path):
	session_id = session_path.name
	return session_path / "simulator" / f"{session_id}_track_screen_position.parquet"