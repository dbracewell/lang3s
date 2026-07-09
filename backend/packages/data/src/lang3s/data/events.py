import enum


class EventType(enum.StrEnum):
    JOB_UPDATE = "job:update"
    AGENT_UPDATE = "agent:update"
    ANALYTICS_UPDATE = "analytics:update"
