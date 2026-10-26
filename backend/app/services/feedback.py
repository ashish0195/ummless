"""User feedback on results ("this looks wrong"). Stored for review; it never changes results."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..ids import new_id
from ..models import FeedbackReport, User
from ..schemas import FeedbackReportCreate, FeedbackReportOut

THANKS = "Thanks — we review every report to improve Comlogue."


def create(db: Session, user: User, body: FeedbackReportCreate) -> FeedbackReportOut:
    report = FeedbackReport(
        id=new_id("fbk"), user_id=user.id, target_type=body.target_type, target_id=body.target_id,
        dimension=body.dimension, reason=body.reason, note=(body.note or "").strip() or None,
    )
    db.add(report)
    db.flush()
    return FeedbackReportOut(id=report.id, message=THANKS)
