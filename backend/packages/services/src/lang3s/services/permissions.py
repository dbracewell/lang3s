from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionAction:
    category: str
    value: str


@dataclass(frozen=True)
class PermissionCategory:
    pass


@dataclass(frozen=True)
class JobPermissions(PermissionCategory):
    list = PermissionAction("job", "list")
    create = PermissionAction("job", "create")
    delete = PermissionAction("job", "delete")
    get = PermissionAction("job", "get")


@dataclass(frozen=True)
class ApiKeyPermissions(PermissionCategory):
    create = PermissionAction("apiKey", "create")
    delete = PermissionAction("apiKey", "delete")


@dataclass(frozen=True)
class UserPermissions(PermissionCategory):
    create = PermissionAction("user", "create")
    list = PermissionAction("user", "list")
    set_role = PermissionAction("user", "set-role")
    ban = PermissionAction("user", "ban")
    impersonate = PermissionAction("user", "impersonate")
    impersonate_admin = PermissionAction("user", "impersonate-admin")
    delete = PermissionAction("user", "delete")
    set_password = PermissionAction("user", "set-password")
    set_email = PermissionAction("user", "set-email")
    get = PermissionAction("user", "get")
    update = PermissionAction("user", "update")


@dataclass(frozen=True)
class SessionPermissions(PermissionCategory):
    list = PermissionAction("session", "list")
    revoke = PermissionAction("session", "revoke")
    delete = PermissionAction("session", "delete")


@dataclass(frozen=True)
class ProjectPermissions(PermissionCategory):
    create = PermissionAction("project", "create")
    share = PermissionAction("project", "share")
    update = PermissionAction("project", "update")
    delete = PermissionAction("project", "delete")


@dataclass(frozen=True)
class MetadataPermissions(PermissionCategory):
    edit = PermissionAction("metadata", "edit")


@dataclass(frozen=True)
class OntologyPermissions(PermissionCategory):
    edit = PermissionAction("metadata", "edit")


class Permissions:
    job = JobPermissions()
    apiKey = ApiKeyPermissions()
    user = UserPermissions()
    session = SessionPermissions()
    project = ProjectPermissions()
    metadata = MetadataPermissions()
    ontology = OntologyPermissions()
