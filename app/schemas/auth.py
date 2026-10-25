from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=80))
    password = fields.String(required=True, validate=validate.Length(min=6, max=128))
    device_name = fields.String(required=False, load_default="Mobile Device")


class UserResponseSchema(Schema):
    id = fields.Integer()
    username = fields.String()
    email = fields.String(allow_none=True)
    role = fields.String()
    is_active = fields.Boolean()
    created_at = fields.String()
    last_login_at = fields.String(allow_none=True)
    member_id = fields.Integer(allow_none=True)


class TokenResponseSchema(Schema):
    token = fields.String()
    token_type = fields.String(dump_default="Bearer")
    expires_at = fields.String()
    user = fields.Nested(UserResponseSchema)
