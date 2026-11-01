from marshmallow import Schema, fields, validate


class StatusUpdateSchema(Schema):
    status = fields.String(
        required=True,
        validate=validate.OneOf([
            "awaiting_confirmation",
            "accepted",
            "declined",
            "in_progress",
            "submitted",
            "completed",
            "blocked",
            "cancelled"
        ])
    )
    note = fields.String(required=False, allow_none=True)
    completion_note = fields.String(required=False, allow_none=True)


class CompleteAssignmentSchema(Schema):
    completion_note = fields.String(required=False, allow_none=True)


class AssignmentResponseSchema(Schema):
    id = fields.Integer()
    task_id = fields.Integer()
    task_title = fields.String(allow_none=True)
    task_priority = fields.String(allow_none=True)
    deadline = fields.String(allow_none=True)
    deadline_formatted = fields.String(allow_none=True)
    event_id = fields.Integer(allow_none=True)
    event_name = fields.String(allow_none=True)
    member_id = fields.Integer()
    member_name = fields.String(allow_none=True)
    member_phone = fields.String(allow_none=True)
    member_reg_no = fields.String(allow_none=True)
    team_id = fields.Integer(allow_none=True)
    team_name = fields.String(allow_none=True)
    assigned_by = fields.Integer()
    assigner_name = fields.String(allow_none=True)
    status = fields.String()
    is_overdue = fields.Boolean()
    assigned_at = fields.String()
    confirmed_at = fields.String(allow_none=True)
    started_at = fields.String(allow_none=True)
    submitted_at = fields.String(allow_none=True)
    completed_at = fields.String(allow_none=True)
    completion_note = fields.String(allow_none=True)
    updated_at = fields.String()
