"""
Workflow job tracking for the n8n automation layer.

A WorkflowJob is created by the ContentAI backend whenever work is handed to
(or announced to) the n8n workflow engine. It records only what n8n needs and
keeps the user ownership link so callbacks can be validated server-side.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON

from app.core.database import Base


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)  # uuid4 hex
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Optional links into existing ContentAI entities (ownership is inherited
    # from user_id — never from callback data).
    content_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    scheduled_post_id = Column(Integer, ForeignKey("scheduled_posts.id"), nullable=True, index=True)

    workflow_type = Column(String(50), nullable=False)  # content_generation | publish | schedule
    status = Column(String(50), default="pending", index=True)
    # pending -> dispatched -> processing -> completed | failed | cancelled

    payload = Column(JSON, nullable=True)   # safe metadata only (no tokens/secrets)
    result = Column(JSON, nullable=True)    # structured result returned by the workflow
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
