from uc_keycloak_sync.config import GroupRule, SyncConfig
from uc_keycloak_sync.main import run_with_clients


class FakeKC:
    def __init__(self, members):
        self.members = members

    def group_members(self, name):
        return self.members[name]


class FakeUC:
    def __init__(self, users, privs):
        self.users, self.privs, self.calls = users, privs, []

    def list_users(self):
        return self.users

    def metastore_id(self):
        return "m1"

    def metastore_privileges(self, mid):
        return self.privs

    def create_user(self, display_name, email, external_id):
        self.calls.append(("create", email, external_id))
        return {"id": "new"}

    def update_user(self, user, *, active, external_id):
        self.calls.append(("update", user["id"], active, external_id))
        return user

    def change_metastore_privileges(self, mid, principal, add, remove):
        self.calls.append(("perm", principal, set(add), set(remove)))


def test_run_applies_plan():
    cfg = SyncConfig(groups=[GroupRule("uc-admins", frozenset({"CREATE CATALOG"}))])
    kc = FakeKC({"uc-admins": [{"id": "s1", "email": "a@x", "firstName": "A"}]})
    uc = FakeUC(users=[{"id": "old", "emails": [{"value": "gone@x"}], "active": True, "externalId": "s9"}],
                privs={"gone@x": {"CREATE CATALOG"}})
    assert run_with_clients(cfg, kc, uc) == 0
    assert ("create", "a@x", "s1") in uc.calls
    assert ("perm", "a@x", {"CREATE CATALOG"}, set()) in uc.calls
    assert ("perm", "gone@x", set(), {"CREATE CATALOG"}) in uc.calls
    assert ("update", "old", False, "s9") in uc.calls


def test_dry_run_makes_no_changes():
    cfg = SyncConfig(groups=[GroupRule("uc-admins", frozenset())], dry_run=True)
    kc = FakeKC({"uc-admins": [{"id": "s1", "email": "a@x"}]})
    uc = FakeUC(users=[], privs={})
    assert run_with_clients(cfg, kc, uc) == 0
    assert uc.calls == []
