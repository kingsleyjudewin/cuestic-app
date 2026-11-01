from marshmallow import Schema, fields, validate


class CommunityCreateSchema(Schema):
    """Validation schema for creating a community."""
    name = fields.String(required=True, validate=validate.Length(min=2, max=120))
    description = fields.String(load_default=None)
    icon = fields.String(load_default=None)
    color = fields.String(load_default=None)
    team_id = fields.Integer(load_default=None)
    is_team_restricted = fields.Boolean(load_default=True)


class ChannelCreateSchema(Schema):
    """Validation schema for creating a channel / group chat in a community."""
    name = fields.String(required=True, validate=validate.Length(min=2, max=80))
    topic = fields.String(load_default=None)
    channel_type = fields.String(
        load_default="text",
        validate=validate.OneOf(["text", "announcement", "group_chat"])
    )


class MessageCreateSchema(Schema):
    """Validation schema for sending a message to a channel."""
    content = fields.String(required=True, validate=validate.Length(min=1, max=5000))
    message_type = fields.String(
        load_default="text",
        validate=validate.OneOf(["text", "announcement", "system"])
    )
    parent_id = fields.Integer(load_default=None)
    attachment_url = fields.String(load_default=None)
