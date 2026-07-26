from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app import security
from app.database import get_session
from app.models.user import User

SessionDep = Annotated[Session, Depends(get_session)]


class NotAuthenticatedError(Exception):
    pass


def load_current_user_for_request(request: Request, session: Session) -> User | None:
    token = request.cookies.get(security.SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return security.verify_session_cookie(token, session)
    except security.SessionSecretNotConfiguredError:
        return None


def get_current_user(request: Request) -> User | None:
    return request.state.user


CurrentUserDep = Annotated[User | None, Depends(get_current_user)]


def require_owner(user: CurrentUserDep) -> User:
    if user is None:
        raise NotAuthenticatedError()
    return user
