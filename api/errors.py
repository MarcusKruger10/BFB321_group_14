"""Central error handling for the whole application.

All errors are handled here, in one place:
  * requests to /api/...  get a JSON error:  {"error": {"code": 404, "message": "..."}}
  * page requests         get a friendly HTML page (templates/error.html)
Stack traces are never shown to the user; they are written to the log instead.
"""
import logging

import pymysql
from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from api.validators import ValidationError

log = logging.getLogger(__name__)

# MySQL / MariaDB error numbers we translate into clear messages
DUPLICATE_ENTRY = 1062          # a UNIQUE value (e.g. SKU) already exists
FOREIGN_KEY_MISSING = 1452      # refers to an id that does not exist
FOREIGN_KEY_IN_USE = 1451       # row is still used by another table
CHECK_FAILED = (3819, 4025)     # CHECK constraint (3819 = MySQL, 4025 = MariaDB)


class ApiError(Exception):
    """Raise this inside an endpoint to return a specific status code,
    for example: raise ApiError(404, "Product 99 not found")."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _wants_json():
    return request.path.startswith("/api/")


def error_response(code, message, details=None):
    if _wants_json():
        body = {"error": {"code": code, "message": message}}
        if details:
            body["error"]["details"] = details
        return jsonify(body), code
    return render_template("error.html", code=code, message=message), code


def register_error_handlers(app):
    """Attach every handler to the Flask app (called once from app.py)."""

    @app.errorhandler(ValidationError)
    def handle_validation(exc):
        log.info("400 on %s %s: %s", request.method, request.path, exc.details)
        return error_response(400, exc.message, exc.details)

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        log.info("%s on %s %s: %s", exc.code, request.method, request.path, exc.message)
        return error_response(exc.code, exc.message, exc.details)

    @app.errorhandler(pymysql.err.IntegrityError)
    def handle_integrity(exc):
        # db.transaction() has already rolled the write back and logged it
        number = exc.args[0] if exc.args else None
        if number == DUPLICATE_ENTRY:
            return error_response(409, "A record with this value already exists",
                                  {"database": str(exc.args[1]) if len(exc.args) > 1 else ""})
        if number == FOREIGN_KEY_MISSING:
            return error_response(400, "A referenced record does not exist (check the ids you sent)")
        if number == FOREIGN_KEY_IN_USE:
            return error_response(409, "This record is still used by other records")
        return error_response(400, "The data breaks a database rule")

    @app.errorhandler(pymysql.err.OperationalError)
    def handle_operational(exc):
        number = exc.args[0] if exc.args else None
        if number in CHECK_FAILED:
            return error_response(400, "A value is outside the allowed range")
        log.exception("Database unavailable")
        return error_response(503, "The database is not available right now")

    @app.errorhandler(HTTPException)
    def handle_http(exc):
        # 404 Not Found, 405 Method Not Allowed, abort(400) etc.
        return error_response(exc.code, exc.description or exc.name)

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return error_response(500, "Something went wrong on the server. The error has been logged.")
