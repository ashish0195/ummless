"""The habit loop: devices & push, the inbox, daily reps, group panels, and the data export."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..core import AppServices
from ..deps import current_user, get_db, get_services
from ..models import User
from ..schemas import (
    DailyRep,
    DailyUpcoming,
    DeviceOut,
    DeviceRegistration,
    NotificationList,
    NotificationOut,
    NotificationRead,
    PanelList,
    UnreadCount,
)
from ..services import daily, group, notifications, users
from ..services import export as export_service

router = APIRouter(prefix="/v1")


# ------------------------------------------------------------------ devices & inbox


@router.post("/devices", response_model=DeviceOut, tags=["notifications"])
def register_device(body: DeviceRegistration, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                    user: User = Depends(current_user)) -> DeviceOut:
    """Upsert this install's push registration (token, permission, timezone). Also sets `Me.timezone`."""
    return notifications.register_device(svc, db, user, body)


@router.delete("/devices/{device_id}", status_code=204, tags=["notifications"])
def delete_device(device_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    notifications.delete_device(db, user, device_id)
    return Response(status_code=204)


@router.get("/notifications", response_model=NotificationList, tags=["notifications"])
def list_notifications(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                       user: User = Depends(current_user)) -> NotificationList:
    return notifications.list_for(db, user, limit)


@router.post("/notifications/read", response_model=UnreadCount, tags=["notifications"])
def read_notifications(body: NotificationRead, db: Session = Depends(get_db),
                       user: User = Depends(current_user)) -> UnreadCount:
    return UnreadCount(unread_count=notifications.mark_read(db, user, body.ids, body.all))


@router.post("/notifications/test", response_model=NotificationOut, tags=["notifications"])
def test_notification(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                      user: User = Depends(current_user)) -> NotificationOut:
    """"Notifications are on": created and pushed right away (ignores quiet hours and the daily cap)."""
    return notifications.send_test(svc, db, user)


@router.post("/notifications/{notification_id}/opened", status_code=204, tags=["notifications"])
def open_notification(notification_id: str, db: Session = Depends(get_db),
                      user: User = Depends(current_user)) -> Response:
    """A tap on a push or an inbox row. Marks it read and resets the nudge back-off."""
    notifications.mark_opened(db, user, notification_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ daily rep


@router.get("/daily", response_model=DailyRep, tags=["daily"])
def get_today(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
              user: User = Depends(current_user)) -> DailyRep:
    return daily.rep_out(svc, db, user, users.today(user))


@router.get("/daily/upcoming", response_model=DailyUpcoming, tags=["daily"])
def get_upcoming(days: int = Query(7), svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                 user: User = Depends(current_user)) -> DailyUpcoming:
    return DailyUpcoming(items=daily.upcoming(svc, db, user, days))


@router.post("/daily/shuffle", response_model=DailyRep, tags=["daily"])
def shuffle_today(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                  user: User = Depends(current_user)) -> DailyRep:
    return daily.shuffle(svc, db, user)


@router.get("/daily/{day}", response_model=DailyRep, tags=["daily"])
def get_day(day: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
            user: User = Depends(current_user)) -> DailyRep:
    return daily.rep_out(svc, db, user, daily.parse_day(user, day))


# ------------------------------------------------------------------ group conversations


@router.get("/group/panels", response_model=PanelList, tags=["group"])
def get_panels(user: User = Depends(current_user)) -> PanelList:
    return group.panels(user)


# ------------------------------------------------------------------ data export


@router.get("/me/export", tags=["me"], responses={200: {"content": {"application/json": {}},
                                                       "description": "Everything stored about you, without audio."}})
def export_me(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
              user: User = Depends(current_user)) -> Response:
    body = json.dumps(export_service.build(svc, db, user), ensure_ascii=False, indent=2)
    return Response(content=body.encode("utf-8"), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{export_service.FILENAME}"',
                             "Cache-Control": "no-store"})
