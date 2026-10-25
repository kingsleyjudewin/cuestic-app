from marshmallow import Schema, fields, validate


class EventCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=2, max=150))
    description = fields.String(required=False, allow_none=True)
    start_at = fields.DateTime(required=True)
    end_at = fields.DateTime(required=False, allow_none=True)
    location = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))
    status = fields.String(
        required=False,
        load_default="upcoming",
        validate=validate.OneOf(["draft", "upcoming", "active", "completed", "cancelled"])
    )


class EventUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=2, max=150))
    description = fields.String(required=False, allow_none=True)
    start_at = fields.DateTime(required=False)
    end_at = fields.DateTime(required=False, allow_none=True)
    location = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))
    status = fields.String(
        required=False,
        validate=validate.OneOf(["draft", "upcoming", "active", "completed", "cancelled"])
    )


class EventResponseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    description = fields.String(allow_none=True)
    start_at = fields.String()
    end_at = fields.String(allow_none=True)
    location = fields.String(allow_none=True)
    status = fields.String()
    created_by = fields.Integer()
    creator_name = fields.String(allow_none=True)
    task_count = fields.Integer()
    created_at = fields.String()
    updated_at = fields.String()
