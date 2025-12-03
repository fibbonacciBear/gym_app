"""API request/response models."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from backend.schema.events import EventType, WeightUnit

class EmitEventRequest(BaseModel):
    """Request to emit an event."""
    event_type: EventType
    payload: Dict[str, Any]

class EmitEventResponse(BaseModel):
    """Response after emitting an event."""
    success: bool
    event_id: str
    timestamp: str
    event_type: EventType
    payload: Dict[str, Any]
    derived: Optional[Dict[str, Any]] = None  # e.g., is_pr, total_volume

class EventRecord(BaseModel):
    """An event record from the store."""
    event_id: str
    timestamp: str
    event_type: str
    payload: Dict[str, Any]

class ProjectionResponse(BaseModel):
    """A projection value."""
    key: str
    data: Optional[Any] = None  # Can be Dict, List, or None

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
