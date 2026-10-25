from marshmallow import Schema, fields, validate


class TeamCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    slug = fields.String(required=False, validate=validate.Length(min=2, max=100))
    description = fields.String(required=False, allow_none=True)
    leader_user_id = fields.Integer(required=False, allow_none=True)


class TeamUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=2, max=100))
    slug = fields.String(required=False, validate=validate.Length(min=2, max=100))
    description = fields.String(required=False, allow_none=True)
    leader_user_id = fields.Integer(required=False, allow_none=True)
    is_active = fields.Boolean(required=False)


class TeamResponseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    slug = fields.String()
    description = fields.String(allow_none=True)
    leader_user_id = fields.Integer(allow_none=True)
    leader_name = fields.String(allow_none=True)
    is_active = fields.Boolean()
    member_count = fields.Integer()
    created_at = fields.String()
    updated_at = fields.String()
