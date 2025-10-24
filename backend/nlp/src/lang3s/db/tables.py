from peewee import *
from pgvector.peewee import VectorField
from playhouse.postgres_ext import JSONField

import lang3s.config as config

database = PostgresqlDatabase(
    "lang3s",
    **{
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
    },
)


class BaseModel(Model):
    class Meta:
        database = database


class User(BaseModel):
    ban_expires = DateTimeField(null=True)
    ban_reason = TextField(null=True)
    banned = BooleanField(constraints=[SQL("DEFAULT false")], null=True)
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    display_username = TextField(null=True)
    email = TextField(unique=True)
    email_verified = BooleanField(constraints=[SQL("DEFAULT false")])
    id = TextField(primary_key=True)
    image = TextField(null=True)
    name = TextField()
    role = TextField(null=True)
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    username = TextField(null=True, unique=True)

    class Meta:
        table_name = "user"


class Account(BaseModel):
    access_token = TextField(null=True)
    access_token_expires_at = DateTimeField(null=True)
    account_id = TextField()
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    id = TextField(primary_key=True)
    id_token = TextField(null=True)
    password = TextField(null=True)
    provider_id = TextField()
    refresh_token = TextField(null=True)
    refresh_token_expires_at = DateTimeField(null=True)
    scope = TextField(null=True)
    updated_at = DateTimeField()
    user = ForeignKeyField(column_name="user_id", field="id", model=User)

    class Meta:
        table_name = "account"


class Documents(BaseModel):
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")], null=True)
    id = TextField(primary_key=True)
    metadata = JSONField(constraints=[SQL("DEFAULT '{}'::json")])
    title = TextField()
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")], null=True)

    class Meta:
        table_name = "documents"


class Session(BaseModel):
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    expires_at = DateTimeField()
    id = TextField(primary_key=True)
    impersonated_by = TextField(null=True)
    ip_address = TextField(null=True)
    token = TextField(unique=True)
    updated_at = DateTimeField()
    user_agent = TextField(null=True)
    user = ForeignKeyField(column_name="user_id", field="id", model=User)

    class Meta:
        table_name = "session"


class Text(BaseModel):
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")], null=True)
    doc = ForeignKeyField(column_name="doc_id", field="id", model=Documents)
    embedding = VectorField(index=True)  # USER-DEFINED
    id = TextField(primary_key=True)
    metadata = JSONField(constraints=[SQL("DEFAULT '{}'::json")])
    text = TextField()
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")], null=True)

    class Meta:
        table_name = "text"
        indexes = (((), False),)


class TextAnnotations(BaseModel):
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")], null=True)
    doc = ForeignKeyField(column_name="doc_id", field="id", model=Documents)
    embedding = VectorField(index=True)  # USER-DEFINED
    end = IntegerField()
    id = UUIDField(
        constraints=[SQL("DEFAULT gen_random_uuid()")], primary_key=True
    )
    metadata = JSONField(constraints=[SQL("DEFAULT '{}'::json")])
    start = IntegerField(index=True)
    text = TextField()
    text_id = ForeignKeyField(column_name="text_id", field="id", model=Text)
    type = TextField(index=True)
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")], null=True)
    value = TextField(index=True)

    class Meta:
        table_name = "text_annotations"


class Verification(BaseModel):
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    expires_at = DateTimeField()
    id = TextField(primary_key=True)
    identifier = TextField()
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    value = TextField()

    class Meta:
        table_name = "verification"
