from marshmallow import Schema, fields, validate


class MemberCreateSchema(Schema):
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=150))
    email = fields.Email(required=False, allow_none=True)
    registration_number = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    class_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    section = fields.String(required=False, allow_none=True, validate=validate.Length(max=20))
    phone_number = fields.String(required=True, validate=validate.Length(min=6, max=30))
    country_code = fields.String(required=False, load_default="+91")
    team_id = fields.Integer(required=True)
    whatsapp_opt_in = fields.Boolean(required=False, load_default=True)
    linked_user_id = fields.Integer(required=False, allow_none=True)


class MemberUpdateSchema(Schema):
    full_name = fields.String(required=False, validate=validate.Length(min=2, max=150))
    registration_number = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    class_name = fields.String(required=False, validate=validate.Length(min=1, max=50))
    section = fields.String(required=False, allow_none=True, validate=validate.Length(max=20))
    phone_number = fields.String(required=False, validate=validate.Length(min=6, max=30))
    country_code = fields.String(required=False)
    team_id = fields.Integer(required=False)
    whatsapp_opt_in = fields.Boolean(required=False)
    is_active = fields.Boolean(required=False)
    linked_user_id = fields.Integer(required=False, allow_none=True)
    email = fields.Email(required=False, allow_none=True)
    role = fields.String(required=False, validate=validate.OneOf(["member", "team_leader", "admin", "president"]))


class MemberAccountCreateSchema(Schema):
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=150))
    registration_number = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    class_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    section = fields.String(required=False, allow_none=True, validate=validate.Length(max=20))
    phone_number = fields.String(required=True, validate=validate.Length(min=6, max=30))
    country_code = fields.String(required=False, load_default="+91")
    team_id = fields.Integer(required=True)
    username = fields.String(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=False, allow_none=True)
    password = fields.String(required=True, validate=validate.Length(min=1, max=128))
    role = fields.String(required=False, load_default="member", validate=validate.OneOf(["member", "team_leader"]))
    whatsapp_opt_in = fields.Boolean(required=False, load_default=True)


class PasswordResetSchema(Schema):
    new_password = fields.String(required=True, validate=validate.Length(min=1, max=128))


class MemberResponseSchema(Schema):
    id = fields.Integer()
    full_name = fields.String()
    email = fields.String(allow_none=True)
    registration_number = fields.String(allow_none=True)
    class_name = fields.String()
    section = fields.String(allow_none=True)
    phone_number = fields.String()
    country_code = fields.String()
    team_id = fields.Integer()
    team_name = fields.String(allow_none=True)
    linked_user_id = fields.Integer(allow_none=True)
    whatsapp_opt_in = fields.Boolean()
    is_active = fields.Boolean()
    has_history = fields.Boolean()
    created_at = fields.String()
    updated_at = fields.String()
