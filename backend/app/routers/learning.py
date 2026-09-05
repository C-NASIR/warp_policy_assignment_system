import re

from fastapi import APIRouter, Query, status
from sqlalchemy import desc, func, select

from app.dependencies import DatabaseSession, HumanSession
from app.models import LearningEvent
from app.schemas import (
    LearningArticleFeedbackSummary,
    LearningEventCreate,
    LearningEventRead,
    LearningInsightsRead,
    LearningSearchMissSummary,
)

submission_router = APIRouter(prefix="/learning-events", tags=["learning"])
insights_router = APIRouter(prefix="/learning-insights", tags=["learning"])

EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
LONG_NUMBER_PATTERN = re.compile(r"\b\d{4,}\b")


def normalize_search_query(query: str) -> str:
    normalized = " ".join(query.casefold().split())
    normalized = EMAIL_PATTERN.sub("[email]", normalized)
    return LONG_NUMBER_PATTERN.sub("[number]", normalized)


@submission_router.post(
    "",
    response_model=LearningEventRead,
    status_code=status.HTTP_201_CREATED,
)
def record_learning_event(
    payload: LearningEventCreate,
    session: DatabaseSession,
    _: HumanSession,
) -> LearningEvent:
    event = LearningEvent(
        event_type=payload.event_type,
        article_id=payload.article_id,
        path=payload.path,
        query=normalize_search_query(payload.query) if payload.query else None,
        helpful=payload.helpful,
        reason=payload.reason,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@insights_router.get("", response_model=LearningInsightsRead)
def get_learning_insights(
    session: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> LearningInsightsRead:
    helpful_count, not_helpful_count = session.execute(
        select(
            func.count().filter(LearningEvent.helpful.is_(True)),
            func.count().filter(LearningEvent.helpful.is_(False)),
        ).where(LearningEvent.event_type == "article_feedback")
    ).one()
    total_feedback = helpful_count + not_helpful_count

    article_rows = session.execute(
        select(
            LearningEvent.article_id,
            func.count().filter(LearningEvent.helpful.is_(True)),
            func.count().filter(LearningEvent.helpful.is_(False)),
        )
        .where(
            LearningEvent.event_type == "article_feedback",
            LearningEvent.article_id.is_not(None),
        )
        .group_by(LearningEvent.article_id)
        .order_by(desc(func.count().filter(LearningEvent.helpful.is_(False))))
        .limit(limit)
    ).all()
    search_rows = session.execute(
        select(
            LearningEvent.query,
            func.count(LearningEvent.id),
            func.max(LearningEvent.created_at),
        )
        .where(
            LearningEvent.event_type == "search_miss",
            LearningEvent.query.is_not(None),
        )
        .group_by(LearningEvent.query)
        .order_by(
            desc(func.count(LearningEvent.id)),
            desc(func.max(LearningEvent.created_at)),
        )
        .limit(limit)
    ).all()

    return LearningInsightsRead(
        total_feedback=total_feedback,
        helpful_percentage=(
            round(helpful_count * 100 / total_feedback, 1)
            if total_feedback
            else None
        ),
        article_feedback=[
            LearningArticleFeedbackSummary(
                article_id=article_id,
                helpful_count=helpful,
                not_helpful_count=not_helpful,
            )
            for article_id, helpful, not_helpful in article_rows
            if article_id is not None
        ],
        unsuccessful_searches=[
            LearningSearchMissSummary(
                query=query,
                count=count,
                last_seen_at=last_seen,
            )
            for query, count, last_seen in search_rows
            if query is not None
        ],
    )
