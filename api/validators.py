"""Input checking for the JSON API.

Every endpoint reads its input through these helpers. If something is wrong
they raise ValidationError, which api/errors.py turns into a
400 Bad Request response that lists every problem, for example:

    {"error": {"code": 400, "message": "Invalid input",
               "details": {"quantity": "must be a whole number greater than 0"}}}
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import request

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class ValidationError(Exception):
    """Raised when the request input is missing or invalid (becomes HTTP 400)."""

    def __init__(self, details, message="Invalid input"):
        super().__init__(message)
        self.message = message
        self.details = details          # {field_name: "what is wrong"}


class Checker:
    """Collects all problems with a request body, so the user sees every
    mistake at once instead of fixing them one by one.

    Usage:
        c = Checker(get_json_body())
        sku = c.string("sku", required=True, max_length=30)
        qty = c.integer("quantity", required=True, minimum=1)
        c.done()                       # raises ValidationError if anything failed
    """

    def __init__(self, data, allowed=None):
        self.data = data
        self.errors = {}
        if allowed is not None:
            unknown = sorted(set(data) - set(allowed))
            if unknown:
                self.errors["_unknown_fields"] = (
                    f"not allowed: {', '.join(unknown)}. Allowed fields: {', '.join(sorted(allowed))}"
                )

    def has(self, field):
        return field in self.data

    def _get(self, field, required):
        if field not in self.data or self.data[field] is None:
            if required:
                self.errors[field] = "is required"
            return None
        return self.data[field]

    def string(self, field, required=False, max_length=255, choices=None):
        value = self._get(field, required)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            self.errors[field] = "must be a non-empty text value"
            return None
        value = value.strip()
        if len(value) > max_length:
            self.errors[field] = f"must be at most {max_length} characters"
        elif choices and value not in choices:
            self.errors[field] = f"must be one of: {', '.join(choices)}"
        return value

    def integer(self, field, required=False, minimum=None, maximum=None):
        value = self._get(field, required)
        if value is None:
            return None
        # bool is a subclass of int in Python, so reject it explicitly
        if isinstance(value, bool) or not isinstance(value, int):
            self.errors[field] = "must be a whole number"
            return None
        if minimum is not None and value < minimum:
            self.errors[field] = f"must be at least {minimum}"
        elif maximum is not None and value > maximum:
            self.errors[field] = f"must be at most {maximum}"
        return value

    def money(self, field, required=False, minimum=Decimal("0")):
        """A rand amount. Returned as Decimal (never float) to match DECIMAL columns."""
        value = self._get(field, required)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            self.errors[field] = "must be a number"
            return None
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            self.errors[field] = "must be a number"
            return None
        if not amount.is_finite() or amount < minimum:
            self.errors[field] = f"must be a number of at least {minimum}"
        elif amount.as_tuple().exponent < -2:
            self.errors[field] = "can have at most 2 decimal places"
        return amount

    def fraction(self, field, required=False):
        """A number strictly between 0 and 1 (for example a service level of 0.95)."""
        value = self._get(field, required)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1:
            self.errors[field] = "must be a number between 0 and 1 (for example 0.95)"
            return None
        return float(value)

    def iso_date(self, field, required=False, future_only=False):
        value = self._get(field, required)
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value) if isinstance(value, str) else None
        except ValueError:
            parsed = None
        if parsed is None:
            self.errors[field] = "must be a date in the format YYYY-MM-DD"
            return None
        if future_only and parsed <= date.today():
            self.errors[field] = "must be a date in the future"
        return parsed

    def boolean(self, field, required=False):
        value = self._get(field, required)
        if value is None:
            return None
        if not isinstance(value, bool):
            self.errors[field] = "must be true or false"
            return None
        return value

    def done(self):
        if self.errors:
            raise ValidationError(self.errors)


def get_json_body():
    """Return the request's JSON object, or raise ValidationError (400)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError(
            {"body": "send a JSON object with the header Content-Type: application/json"},
            message="Request body must be JSON",
        )
    return data


def query_int(name, default, minimum, maximum):
    """Read a whole-number query parameter such as ?page=2, with limits."""
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: "must be a whole number"})
    if not minimum <= value <= maximum:
        raise ValidationError({name: f"must be between {minimum} and {maximum}"})
    return value


def query_choice(name, choices):
    """Read an optional query parameter that must be one of `choices`."""
    value = request.args.get(name) or None
    if value is not None and value not in choices:
        raise ValidationError({name: f"must be one of: {', '.join(choices)}"})
    return value


def pagination():
    """Read ?page= and ?size= and return (page, size, offset)."""
    page = query_int("page", 1, 1, 100_000)
    size = query_int("size", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    return page, size, (page - 1) * size
