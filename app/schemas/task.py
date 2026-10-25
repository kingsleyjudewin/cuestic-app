from marshmallow import Schema, fields, validate


class TaskCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=2, max=200))
    description = fields.String(required=False, allow_none=True)
    priority = fields.String(
        required=False,
        load_default="medium",
        validate=validate.OneOf(["low", "medium", "high", "urgent"])
    )
    deadline = fields.DateTime(required=True)
    member_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))


class TaskUpdateSchema(Schema):
    title = fields.String(required=False, validate=validate.Length(min=2, max=200))
    description = fields.String(required=False, allow_none=True)
    priority = fields.String(
        required=False,
        validate=validate.OneOf(["low", "medium", "high", "urgent"])
    )
    deadline = fields.DateTime(required=False)
    is_cancelled = fields.Boolean(required=False)


class AddAssignmentsSchema(Schema):
    member_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))


class TaskResponseSchema(Schema):
    id = fields.Integer()
    event_id = fields.Integer()
    event_name = fields.String(allow_none=True)
    title = fields.String()
    description = fields.String(allow_none=True)
    priority = fields.String()
    deadline = fields.String()
    deadline_formatted = fields.String()
    created_by = fields.Integer()
    creator_name = fields.String(allow_none=True)
    is_cancelled = fields.Boolean()
    assignee_count = fields.Integer()
    created_at = fields.String()
    updated_at = fields.String()
