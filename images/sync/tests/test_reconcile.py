from uc_keycloak_sync.config import GroupRule
from uc_keycloak_sync.reconcile import build_desired, plan

ADMINS = GroupRule("uc-admins", frozenset({"CREATE CATALOG"}))
USERS = GroupRule("uc-users", frozenset())


def kc(email, first="A", last="B"):
    return {"id": f"sub-{email}", "email": email, "firstName": first, "lastName": last, "username": email}


def uc(email, uid="u1", active=True, external_id="__default__"):
    return {"id": uid, "displayName": email, "emails": [{"value": email, "primary": True}], "active": active,
            "externalId": f"sub-{email}" if external_id == "__default__" else external_id}


def test_build_desired_merges_privileges_and_skips_missing_email():
    desired, warnings = build_desired([(ADMINS, [kc("a@x.io")]),
                                       (USERS, [kc("a@x.io"), kc("b@x.io"), {"id": "noemail", "username": "svc"}])])
    assert desired["a@x.io"].privileges == {"CREATE CATALOG"}
    assert desired["b@x.io"].privileges == set()
    assert desired["a@x.io"].display_name == "A B"
    assert desired["a@x.io"].external_id == "sub-a@x.io"
    assert warnings == ["skipping Keycloak user 'svc' (id noemail): no email"]


def test_build_desired_lowercases_email():
    desired, _ = build_desired([(USERS, [kc("Mixed@X.io")])])
    assert list(desired) == ["mixed@x.io"]


def test_plan_creates_missing_and_grants():
    desired, _ = build_desired([(ADMINS, [kc("a@x.io")])])
    p = plan(desired, existing_users=[], existing_privileges={}, managed_privileges={"CREATE CATALOG"}, deactivate_removed=True)
    assert [c.email for c in p.create] == ["a@x.io"]
    assert p.grant == {"a@x.io": {"CREATE CATALOG"}}
    assert p.revoke == {} and p.deactivate == [] and p.update == []


def test_plan_reactivates_and_sets_external_id():
    desired, _ = build_desired([(USERS, [kc("a@x.io")])])
    p = plan(desired, [uc("a@x.io", active=False, external_id=None)], {}, set(), True)
    assert p.create == []
    assert len(p.update) == 1 and p.update[0].active is True and p.update[0].external_id == "sub-a@x.io"


def test_plan_no_update_when_in_sync():
    desired, _ = build_desired([(USERS, [kc("a@x.io")])])
    p = plan(desired, [uc("a@x.io")], {}, set(), True)
    assert p.is_empty()


def test_plan_revokes_only_managed_privileges():
    desired, _ = build_desired([(USERS, [kc("a@x.io")])])
    p = plan(desired, [uc("a@x.io")], {"a@x.io": {"CREATE CATALOG", "USE CATALOG"}}, {"CREATE CATALOG"}, True)
    assert p.revoke == {"a@x.io": {"CREATE CATALOG"}}


def test_plan_deactivates_managed_users_not_desired_and_revokes():
    p = plan({}, [uc("gone@x.io"), uc("manual@x.io", uid="u2", external_id=None), uc("admin", uid="u3", external_id=None)],
             {"gone@x.io": {"CREATE CATALOG"}}, {"CREATE CATALOG"}, True)
    assert [u["id"] for u in p.deactivate] == ["u1"]
    assert p.revoke == {"gone@x.io": {"CREATE CATALOG"}}


def test_plan_never_touches_admin_even_if_external_id_set():
    p = plan({}, [uc("admin", external_id="sub-admin")], {}, set(), True)
    assert p.deactivate == []


def test_plan_deactivate_disabled():
    p = plan({}, [uc("gone@x.io")], {}, set(), deactivate_removed=False)
    assert p.deactivate == []


def test_plan_skips_already_inactive():
    p = plan({}, [uc("gone@x.io", active=False)], {}, set(), True)
    assert p.deactivate == []
