from marshmallow import Schema, fields, validate


class ReminderCreateSchema(Schema):
    reminder_type = fields.String(
        required=True,
        validate=validate.OneOf([
            "confirmation_reminder",
            "deadline_reminder",
            "overdue_reminder",
            "custom"
        ])
    )
    scheduled_at = fields.DateTime(required=False)


class ReminderResponseSchema(Schema):
    id = fields.Integer()
    assignment_id = fields.Integer()
    task_id = fields.Integer(allow_none=True)
    task_title = fields.String(allow_none=True)
    member_id = fields.Integer(allow_none=True)
    member_name = fields.String(allow_none=True)
    reminder_type = fields.String()
    scheduled_at = fields.String()
    status = fields.String()
    deduplication_key = fields.String()
    created_at = fields.String()
    actioned_at = fields.String(allow_none=True)
