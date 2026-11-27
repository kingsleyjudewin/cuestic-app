"""Visitor mode: a shared demo login that can explore every admin screen on an empty workspace.

A visitor account is a normal ``admin`` account whose username is listed in the
``VISITOR_USERNAMES`` setting (default: ``visitor``). The frontend routes it exactly like an
administrator, so no separate screens exist. The server keeps it isolated from real data:

* Reads: every ORM query made while serving a visitor request gets a ``WHERE false`` criterion
  on every table, so lists come back empty, counts are zero and detail lookups 404. The one
  exception is the visitor's own ``users`` row and ``api_tokens`` rows, which login, ``/auth/me``
  and logout need.
* Shared reference data: the built-in (``is_default``) MC templates and their segments are
  readable, so the template picker and programme builder have something to show.
* AI tools: the stateless AI endpoints (MC script/segment generation, rewrite, report AI assist,
  poster analysis) accept POSTs from a visitor, because they only return generated text and save
  nothing. Database writes stay blocked during those requests too. They are capped per visitor
  account (``VISITOR_AI_CALLS_PER_HOUR``, default 20) to protect the AI quota.
* Writes: other non-GET requests are rejected with ``403 VISITOR_READ_ONLY`` before the view runs
  (except logout), and any flush or bulk INSERT/UPDATE/DELETE attempted during a visitor request
  raises the same error, which also covers GET handlers that lazily seed data.
* Caches: the API's in-memory caches hold real data and are shared by every request in the
  process. Every cache read and write is skipped for visitor requests (``caching_allowed()``),
  so a visitor never sees cached real data and never fills a cache with empty results.
"""
import threading
import time
from collections import deque

from flask import has_request_context, current_app, request
from sqlalchemy import event, false
from sqlalchemy.orm import Session, with_loader_criteria

from app.utils.errors import AppError

# Endpoints a visitor may call with a non-GET method. Logout only revokes the visitor's own token.
VISITOR_WRITE_ALLOWED_ENDPOINTS = frozenset({"auth.logout"})
# Stateless AI endpoints a visitor may POST to. They return generated text and never save it.
VISITOR_AI_ENDPOINTS = frozenset({
    "mc.ai_generate_full_script",
    "mc.ai_generate_segment",
    "mc.ai_rewrite_dialogue",
    "mc.ai_assist",
    "documentation.ai_assist",
    "documentation.analyze_poster",
    "documentation.analyze_feedback",
    "documentation.simulate_impact_analysis",
    "documentation.simulate_feedback_analysis",
})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class VisitorReadOnlyError(AppError):
    status_code = 403
    code = "VISITOR_READ_ONLY"


READ_ONLY_MESSAGE = "Visitor mode is read-only. Sign in with a club account to make changes."


class VisitorAiLimitError(AppError):
    status_code = 429
    code = "VISITOR_AI_LIMIT"


# Sliding one-hour window of AI call timestamps per visitor user id. In-memory, so it is per
# process; production runs a single gunicorn worker (see gunicorn.conf.py).
_ai_calls: dict = {}
_ai_lock = threading.Lock()


def _check_ai_quota(user_id: int):
    limit = int(current_app.config.get("VISITOR_AI_CALLS_PER_HOUR", 20))
    now = time.monotonic()
    with _ai_lock:
        calls = _ai_calls.setdefault(user_id, deque())
        while calls and now - calls[0] >= 3600:
            calls.popleft()
        if len(calls) >= limit:
            retry_after = int(3600 - (now - calls[0])) + 1
            raise VisitorAiLimitError(
                f"Visitor mode allows {limit} AI generations per hour. Try again in about "
                f"{max(1, retry_after // 60)} minutes.",
                details={"retry_after_seconds": retry_after},
            )
        calls.append(now)


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
    if request.method in _SAFE_METHODS or writes_allowed:
        return
    if request.endpoint in VISITOR_AI_ENDPOINTS:
        _check_ai_quota(user.id)
        return
    raise VisitorReadOnlyError(READ_ONLY_MESSAGE)


def _visitor_criteria(user_id: int):
    from app.extensions import db
    from app.models.user import User, ApiToken
    from app.models.mc_script import McTemplate, McTemplateSegment

    default_template_ids = db.select(McTemplate.id).where(McTemplate.is_default.is_(True))
    options = []
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if cls is User:
            crit = User.id == user_id
        elif cls is ApiToken:
            crit = ApiToken.user_id == user_id
        elif cls is McTemplate:
            crit = McTemplate.is_default.is_(True)
        elif cls is McTemplateSegment:
            crit = McTemplateSegment.template_id.in_(default_template_ids)
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
