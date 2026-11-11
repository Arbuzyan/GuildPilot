import asyncio
from app.core.time import utc_now


from app.db.database import SessionLocal
from app.db.models import ScheduledDealPost
from app.deals.schedule_queries import get_pending_schedules
from app.discord.sales_publisher import publish_scheduled_deal

async def scheduler_loop(
    client,
    check_interval_seconds: int = 30,
):
    scheduler_started_at = utc_now()

    print(
        f"[SCHEDULER] Loop started "
        f"(interval={check_interval_seconds}s)"
    )

    print(
        f"[SCHEDULER] Startup time: "
        f"{scheduler_started_at}"
    )

    while True:
        db = SessionLocal()

        try:
            now = utc_now()

            pending_schedules = get_pending_schedules(db)

            for schedule in pending_schedules:
                schedule_id = schedule.id
                deal_id = schedule.deal_id

                # Старые расписания, которые уже прошли
                # до запуска бота, пропускаем.
                if schedule.scheduled_at < scheduler_started_at:
                    schedule.status = "skipped"

                    print(
                        f"[SCHEDULER] Schedule {schedule_id}: "
                        f"skipped old schedule "
                        f"(scheduled_at={schedule.scheduled_at})"
                    )

                    db.commit()
                    continue

                # Будущие расписания пока не трогаем.
                if schedule.scheduled_at > now:
                    continue

                print(
                    f"[SCHEDULER] Due schedule found: "
                    f"ID={schedule_id}, Deal={deal_id}"
                )

                is_burst = schedule.status == "burst_pending"
                schedule.status = "processing_burst" if is_burst else "processing"
                db.commit()

                success, message = await publish_scheduled_deal(
                    client=client,
                    deal_id=deal_id,
                    bypass_daily_limit=is_burst,
                )

                # A moderator may cancel this schedule while publication is
                # in progress. Refresh before writing the final state so the
                # scheduler does not overwrite that cancellation.
                db.refresh(schedule)
                if schedule.status == "cancelled":
                    print(
                        f"[SCHEDULER] Schedule {schedule_id}: "
                        "cancellation detected after publication attempt"
                    )
                    continue

                if success:
                    schedule.status = "completed"

                    print(
                        f"[SCHEDULER] Schedule {schedule_id}: "
                        f"completed"
                    )

                elif message.startswith("LIMIT_REACHED:"):
                    schedule.status = "limit_reached"

                    print(
                        f"[SCHEDULER] Schedule {schedule_id}: "
                        f"limit reached — {message}"
                    )

                else:
                    schedule.status = "failed"

                    print(
                        f"[SCHEDULER] Schedule {schedule_id}: "
                        f"failed — {message}"
                    )

                db.commit()

        except Exception as error:
            db.rollback()
            print(f"[SCHEDULER] Error: {error}")

        finally:
            db.close()

        await asyncio.sleep(check_interval_seconds)