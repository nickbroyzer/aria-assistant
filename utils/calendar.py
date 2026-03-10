"""
Google Calendar integration: service auth, available slots.
"""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from utils.constants import (
    CALENDAR_TOKEN, CALENDAR_CREDS, CALENDAR_SCOPES,
    BUSINESS_HOURS, SLOT_DURATION,
)
from utils.config import _integ_val


def _get_calendar_id():
    return _integ_val("CALENDAR_ID") or "primary"


def get_calendar_service():
    """Return an authorized Google Calendar service."""
    creds = None
    if os.path.exists(CALENDAR_TOKEN):
        creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN, CALENDAR_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(CALENDAR_TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def get_available_slots(days_ahead=7):
    """Return available 1-hour slots over the next N weekdays during business hours."""
    service = get_calendar_service()
    now = datetime.now(timezone.utc)
    end_range = now + timedelta(days=days_ahead * 2)  # extra buffer for weekends

    # Fetch existing events
    events_result = service.events().list(
        calendarId=_get_calendar_id(),
        timeMin=now.isoformat(),
        timeMax=end_range.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    busy = []
    for e in events_result.get("items", []):
        s = e.get("start", {}).get("dateTime")
        en = e.get("end", {}).get("dateTime")
        if s and en:
            busy.append((datetime.fromisoformat(s), datetime.fromisoformat(en)))

    # Generate candidate slots
    slots = []
    pacific = ZoneInfo("America/Los_Angeles")
    day = datetime.now(pacific).replace(hour=0, minute=0, second=0, microsecond=0)
    days_found = 0
    while days_found < days_ahead:
        day += timedelta(days=1)
        if day.weekday() >= 5:  # skip weekends
            continue
        days_found += 1
        for hour in range(BUSINESS_HOURS["start"], BUSINESS_HOURS["end"]):
            slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=1)
            slot_start_utc = slot_start.astimezone(timezone.utc)
            slot_end_utc = slot_end.astimezone(timezone.utc)
            # Check for conflicts
            conflict = any(
                s < slot_end_utc and e > slot_start_utc for s, e in busy
            )
            if not conflict:
                slots.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "label": slot_start.strftime("%A, %B %d · %I:%M %p").replace(" 0", " ")
                })
    return slots[:10]  # return up to 10 slots
