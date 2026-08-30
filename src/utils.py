import json
import os
from datetime import datetime, date
import pytz
import re
import pandas as pd
from typing import List, Dict, Any

from src.models import ScheduleRow

def get_timezone_aware_today() -> date:
    """Returns today's date in a timezone-aware manner (UTC for consistency)."""
    # Using UTC for deterministic behavior across different environments
    return datetime.now(pytz.utc).date()

def load_schedule(file_path: str) -> List[ScheduleRow]:
    """Loads the schedule from a CSV file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Schedule file not found: {file_path}")
    df = pd.read_csv(file_path)
    df['post_date'] = pd.to_datetime(df['post_date']).dt.tz_localize(pytz.utc)
    return [ScheduleRow(**row) for row in df.to_dict(orient='records')]

def load_posted_ids(file_path: str) -> List[str]:
    """Loads already posted IDs from a JSON file."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return []
    with open(file_path, 'r') as f:
        return json.load(f)

def save_posted_id(file_path: str, row_id: str):
    """Saves a new posted ID to the JSON file."""
    posted_ids = load_posted_ids(file_path)
    if row_id not in posted_ids:
        posted_ids.append(row_id)
    with open(file_path, 'w') as f:
        json.dump(posted_ids, f, indent=2)

def append_trace(file_path: str, trace_data: Dict[str, Any]):
    """Appends a trace entry to the JSONL file."""
    with open(file_path, 'a') as f:
        f.write(json.dumps(trace_data, default=str) + '\n')

def extract_urls_and_mentions(text: str) -> Dict[str, List[str]]:
    """Extracts URLs and @mentions from a given text."""
    urls = re.findall(r'https?://[^\s]+', text)
    mentions = re.findall(r'@(\w+)', text)
    return {"urls": urls, "mentions": mentions}

def get_env_var(name: str, default: Optional[str] = None) -> str:
    """Safely get environment variable, raising error if not found and no default."""
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Environment variable '{name}' not set.")
    return value
