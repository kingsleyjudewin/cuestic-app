"""Visitor mode: a shared demo login that can explore every admin screen on an empty workspace.

A visitor account is a normal ``admin`` account whose username is listed in the
``VISITOR_USERNAMES`` setting (default: ``visitor``). The frontend routes it exactly like an
administrator, so no separate screens exist. The server keeps it isolated from real data:

* Reads: every ORM query made while serving a visitor request gets a ``WHERE false`` criterion
  on every table, so lists come back empty, counts are zero and detail lookups 404. The one
  exception is the visitor's own ``users`` row and ``api_tokens`` rows, which login, ``/auth/me``
  and logout need.
* Writes: non-GET requests are rejected with ``403 VISITOR_READ_ONLY`` before the view runs
  (except logout), and any flush or bulk INSERT/UPDATE/DELETE attempted during a visitor request
  raises the same error, which also covers GET handlers that lazily seed data.
* Caches: the API's in-memory caches hold real data and are shared by every request in the
  process. Every cache read and write is skipped for visitor requests (``caching_allowed()``),
  so a visitor never sees cached real data and never fills a cache with empty results.
"""
from flask import has_request_context, current_app, request
from sqlalchemy import event, false
from sqlalchemy.orm import Session, with_loader_criteria

from app.utils.errors import AppError

# Endpoints a visitor may call with a non-GET method. Logout only revokes the visitor's own token.
VISITOR_WRITE_ALLOWED_ENDPOINTS = frozenset({"auth.logout"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class VisitorReadOnlyError(AppError):
    status_code = 403
    code = "VISITOR_READ_ONLY"


READ_ONLY_MESSAGE = "Visitor mode is read-only. Sign in with a club account to make changes."


def visitor_usernames(app=None) -> frozenset:
    app = app or current_app
    raw = app.config.get("VISITOR_USERNAMES", "visitor") or ""
    return frozenset(u.strip().lower() for u in raw.split(",") if u.strip())


def is_visitor_user(user) -> bool:
    if user is None or not getattr(user, "username", None):
        return False
    try:
        return user.username.lower() in visitor_usernames()
    except RuntimeError:  # no application context
        return False


_ENV_KEY = "cuestic.visitor"


def _state():
    """Visitor state for the current request, kept in the WSGI environ so it is strictly
    request-scoped (``flask.g`` belongs to the app context, which can outlive one request)."""
    if not has_request_context():
        return None
    return request.environ.get(_ENV_KEY)


def is_visitor_request() -> bool:
    return _state() is not None


def caching_allowed() -> bool:
    """False while serving a visitor: shared in-memory caches must be neither read nor written."""
    return not is_visitor_request()


def enter_visitor_mode(user):
    """Called by @token_required once the visitor is authenticated."""
    writes_allowed = request.endpoint in VISITOR_WRITE_ALLOWED_ENDPOINTS
    request.environ[_ENV_KEY] = {"user_id": user.id, "writes_allowed": writes_allowed, "options": None}
    if request.method not in _SAFE_METHODS and not writes_allowed:
        raise VisitorReadOnlyError(READ_ONLY_MESSAGE)


def _visitor_criteria(user_id: int):
    from app.extensions import db
    from app.models.user import User, ApiToken

    options = []
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if cls is User:
            crit = User.id == user_id
        elif cls is ApiToken:
            crit = ApiToken.user_id == user_id
        else:
            crit = false()
        options.append(with_loader_criteria(cls, crit, include_aliases=True))
    return options


def _on_orm_execute(orm_state):
    visitor = _state()
    if visitor is None:
        return
    if orm_state.is_select:
        if visitor["options"] is None:
            visitor["options"] = _visitor_criteria(visitor["user_id"])
        orm_state.statement = orm_state.statement.options(*visitor["options"])
    elif (orm_state.is_insert or orm_state.is_update or orm_state.is_delete) and not visitor["writes_allowed"]:
        raise VisitorReadOnlyError(READ_ONLY_MESSAGE)


def _on_before_flush(session, flush_context, instances):
    visitor = _state()
    if visitor is None or visitor["writes_allowed"]:
        return
    if session.new or session.dirty or session.deleted:
        session.expunge_all()  # nothing a visitor touched may reach the database
        raise VisitorReadOnlyError(READ_ONLY_MESSAGE)


_installed = False


def install_visitor_mode():
    """Register the session hooks once per process."""
    global _installed
    if _installed:
        return
    event.listen(Session, "do_orm_execute", _on_orm_execute)
    event.listen(Session, "before_flush", _on_before_flush)
    _installed = True
