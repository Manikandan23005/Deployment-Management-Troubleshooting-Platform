# --- Thread-Safe Incident & Audit State Store ---
import threading
from typing import Dict, List, Optional
import datetime
from app.agent.models import AutonomousIncident, IncidentTimelineEntry, IncidentStatus

class IncidentStore:
    """In-memory thread-safe storage and indexing for autonomous incidents and their audit timelines."""

    def __init__(self):
        self._lock = threading.Lock()
        self._incidents: Dict[str, AutonomousIncident] = {}

    def save(self, incident: AutonomousIncident) -> AutonomousIncident:
        """Saves or updates an AutonomousIncident record."""
        with self._lock:
            incident.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._incidents[incident.incident_id] = incident
            return incident

    def get(self, incident_id: str) -> Optional[AutonomousIncident]:
        """Retrieves an AutonomousIncident by ID."""
        with self._lock:
            return self._incidents.get(incident_id)

    def list_all(self, limit: int = 50) -> List[AutonomousIncident]:
        """Lists all registered incidents sorted by newest first."""
        with self._lock:
            items = list(self._incidents.values())
            items.sort(key=lambda x: x.created_at, reverse=True)
            return items[:limit]

    def add_timeline_event(
        self,
        incident_id: str,
        stage: IncidentStatus,
        message: str,
        details: Optional[Dict] = None
    ) -> Optional[AutonomousIncident]:
        """Appends a new chronological audit event to the incident timeline."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return None
            
            entry = IncidentTimelineEntry(
                stage=stage,
                message=message,
                details=details or {}
            )
            incident.timeline.append(entry)
            incident.status = stage
            incident.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return incident

    def update_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        final_outcome: Optional[str] = None
    ) -> Optional[AutonomousIncident]:
        """Updates the status and outcome of an incident."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return None
            incident.status = status
            if final_outcome:
                incident.final_outcome = final_outcome
            incident.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return incident

    def clear(self):
        """Clears stored incidents (primarily for testing)."""
        with self._lock:
            self._incidents.clear()

incident_store = IncidentStore()
