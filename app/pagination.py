from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, TypeVar

from fastapi import Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

T = TypeVar("T")

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 500


@dataclass(frozen=True)
class PageParameters:
    limit: int
    offset: int


def get_page_parameters(
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_LIMIT, description="Maximum items to return"),
    ] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of matching items to skip"),
    ] = 0,
) -> PageParameters:
    return PageParameters(limit=limit, offset=offset)


Pagination = Annotated[PageParameters, Depends(get_page_parameters)]


def paginate_scalars(
    session: Session,
    statement: Select[tuple[T]],
    pagination: PageParameters,
    response: Response,
) -> list[T]:
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    set_pagination_headers(
        response,
        total=int(total or 0),
        pagination=pagination,
    )
    return list(
        session.scalars(
            statement.limit(pagination.limit).offset(pagination.offset)
        )
    )


def paginate_sequence(
    items: list[T],
    pagination: PageParameters,
    response: Response,
) -> list[T]:
    set_pagination_headers(
        response,
        total=len(items),
        pagination=pagination,
    )
    return items[pagination.offset : pagination.offset + pagination.limit]


def set_pagination_headers(
    response: Response,
    *,
    total: int,
    pagination: PageParameters,
) -> None:
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(pagination.limit)
    response.headers["X-Offset"] = str(pagination.offset)
