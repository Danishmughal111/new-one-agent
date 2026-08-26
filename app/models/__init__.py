"""SQLAlchemy ORM models for the AI Company OS domain.

Importing these classes registers their table metadata on ``Base.metadata``,
which is required before ``create_all`` or Alembic autogenerate can see them.
"""

from app.models.base import Base, TimestampMixin, new_uuid, utcnow
from app.models.agent import Agent
from app.models.article import Article
from app.models.audit_log import AuditLog
from app.models.blogger_connection import BloggerConnection
from app.models.affiliate_offer import AffiliateOfferRecord
from app.models.department import Department
from app.models.objective import Objective
from app.models.product import Product
from app.models.task import Task
from app.models.task_status_history import TaskStatusHistory
from app.models.workflow import Workflow

__all__ = [
    "Base",
    "TimestampMixin",
    "new_uuid",
    "utcnow",
    "Agent",
    "AffiliateOfferRecord",
    "Article",
    "AuditLog",
    "BloggerConnection",
    "Department",
    "Objective",
    "Product",
    "Task",
    "TaskStatusHistory",
    "Workflow",
]