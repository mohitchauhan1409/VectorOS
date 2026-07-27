"""GoogleCalendarProvider — real calendar via the Google Calendar API (free).

Uses ``freebusy().query`` for busy intervals and ``events().insert`` to book,
attaching a Google Meet link. Auth is OAuth: a one-time consent stores a token
file that's reused (and auto-refreshed) after. See README/.env for setup.

The Google client libs are imported lazily, so the rest of Connect/Inbox works
without them installed until you actually switch the provider to ``google``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from modules.common.logger import get_logger
from modules.pulse.scheduling import config
from modules.pulse.scheduling.schemas import BookingRequest, BookingResult, BusyInterval

logger = get_logger("pulse.scheduling.google")

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarProvider:
    name = "google"

    def __init__(self) -> None:
        self.calendar_id = config.GOOGLE_CALENDAR_ID
        self._service = None

    # -- auth / health ------------------------------------------------------
    def health_check(self) -> tuple[bool, str]:
        if not config.GOOGLE_OAUTH_CLIENT_FILE and not config.GOOGLE_OAUTH_TOKEN_FILE:
            return False, "not configured: set GOOGLE_OAUTH_CLIENT_FILE / GOOGLE_OAUTH_TOKEN_FILE"
        try:
            self._svc()
        except Exception as exc:  # noqa: BLE001
            return False, f"google auth/deps error: {exc}"
        return True, f"google calendar '{self.calendar_id}' ready"

    def _svc(self):
        """Build (and cache) an authorized Calendar service."""
        if self._service is not None:
            return self._service
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Google libs missing. pip install google-api-python-client "
                "google-auth-httplib2 google-auth-oauthlib") from exc

        creds = None
        token_file = config.GOOGLE_OAUTH_TOKEN_FILE
        if token_file:
            import os
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, _SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            if not config.GOOGLE_OAUTH_CLIENT_FILE:
                raise RuntimeError("No valid token and no GOOGLE_OAUTH_CLIENT_FILE for consent.")
            flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_OAUTH_CLIENT_FILE, _SCOPES)
            creds = flow.run_local_server(port=0)
            if token_file:
                with open(token_file, "w") as f:
                    f.write(creds.to_json())
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    # -- provider interface -------------------------------------------------
    def free_busy(self, start: datetime, end: datetime) -> list[BusyInterval]:
        body = {"timeMin": start.astimezone(timezone.utc).isoformat(),
                "timeMax": end.astimezone(timezone.utc).isoformat(),
                "items": [{"id": self.calendar_id}]}
        resp = self._svc().freebusy().query(body=body).execute()
        cal = resp.get("calendars", {}).get(self.calendar_id, {})
        out: list[BusyInterval] = []
        for b in cal.get("busy", []):
            out.append(BusyInterval(start=datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                                    end=datetime.fromisoformat(b["end"].replace("Z", "+00:00"))))
        return out

    def create_event(self, request: BookingRequest) -> BookingResult:
        event = {
            "summary": request.title,
            "description": request.description,
            "start": {"dateTime": request.slot.start.isoformat()},
            "end": {"dateTime": request.slot.end.isoformat()},
            "attendees": [{"email": request.attendee_email}] if request.attendee_email else [],
        }
        kwargs = {"calendarId": self.calendar_id, "body": event, "sendUpdates": "all"}
        if config.MEETING_ADD_CONFERENCE:
            event["conferenceData"] = {"createRequest": {
                "requestId": f"pulse-{request.slot.iso()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
            kwargs["conferenceDataVersion"] = 1
        try:
            created = self._svc().events().insert(**kwargs).execute()
        except Exception as exc:  # noqa: BLE001
            return BookingResult(ok=False, error=f"google insert failed: {exc}")
        join = created.get("hangoutLink", "") or (created.get("conferenceData", {})
                                                  .get("entryPoints", [{}])[0].get("uri", ""))
        return BookingResult(ok=True, event_id=created.get("id", ""), join_url=join)

    def cancel_event(self, event_id: str) -> bool:
        if not event_id:
            return False
        try:
            self._svc().events().delete(calendarId=self.calendar_id, eventId=event_id,
                                        sendUpdates="all").execute()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("google delete failed for %s: %s", event_id, exc)
            return False

    def update_event(self, event_id: str, request: BookingRequest) -> BookingResult:
        if not event_id:
            return BookingResult(ok=False, error="no event id")
        body = {"start": {"dateTime": request.slot.start.isoformat()},
                "end": {"dateTime": request.slot.end.isoformat()}}
        try:
            updated = self._svc().events().patch(
                calendarId=self.calendar_id, eventId=event_id, body=body,
                sendUpdates="all").execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("google patch failed for %s: %s", event_id, exc)
            return BookingResult(ok=False, error=f"patch failed: {exc}")
        join = updated.get("hangoutLink", "") or (updated.get("conferenceData", {})
                                                  .get("entryPoints", [{}])[0].get("uri", ""))
        return BookingResult(ok=True, event_id=updated.get("id", event_id), join_url=join)
