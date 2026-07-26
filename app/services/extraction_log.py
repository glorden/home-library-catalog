from sqlmodel import Session, func, select

from app.models.extraction_call import ExtractionCall
from app.timeutil import utcnow


def count_calls_today(session: Session) -> int:
    start_of_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return session.exec(
        select(func.count())
        .select_from(ExtractionCall)
        .where(ExtractionCall.created_at >= start_of_day)
    ).one()


def log_call(
    session: Session,
    *,
    provider: str,
    model_name: str,
    image_count: int,
    success: bool,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    error_message: str | None = None,
) -> None:
    session.add(
        ExtractionCall(
            provider=provider,
            model_name=model_name,
            image_count=image_count,
            success=success,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            error_message=error_message,
        )
    )
    session.commit()
