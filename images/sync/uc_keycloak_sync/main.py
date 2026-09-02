from __future__ import annotations

import logging
import sys

from .config import Settings, SyncConfig, load_config
from .keycloak import KeycloakClient
from .reconcile import build_desired, plan
from .unitycatalog import UnityCatalogClient, mint_admin_token

log = logging.getLogger("uc-keycloak-sync")


def run_with_clients(cfg: SyncConfig, kc, uc) -> int:
    members_by_rule = [(rule, kc.group_members(rule.name)) for rule in cfg.groups]
    desired, warnings = build_desired(members_by_rule)
    for w in warnings:
        log.warning(w)
    log.info("desired users: %d", len(desired))

    existing = uc.list_users()
    metastore = uc.metastore_id()
    privileges = uc.metastore_privileges(metastore)
    p = plan(desired, existing, privileges, cfg.managed_privileges, cfg.deactivate_removed)

    log.info("plan: create=%d update=%d deactivate=%d grant=%d revoke=%d",
             len(p.create), len(p.update), len(p.deactivate), len(p.grant), len(p.revoke))
    if p.is_empty():
        log.info("nothing to do")
        return 0
    if cfg.dry_run:
        for d in p.create:
            log.info("[dry-run] create %s", d.email)
        for u in p.update:
            log.info("[dry-run] update %s active=%s", u.user.get("id"), u.active)
        for u in p.deactivate:
            log.info("[dry-run] deactivate %s", u.get("id"))
        for email, privs in p.grant.items():
            log.info("[dry-run] grant %s %s", email, sorted(privs))
        for email, privs in p.revoke.items():
            log.info("[dry-run] revoke %s %s", email, sorted(privs))
        return 0

    for d in p.create:
        log.info("creating user %s", d.email)
        uc.create_user(d.display_name, d.email, d.external_id)
    for u in p.update:
        log.info("updating user %s (active=%s)", u.user.get("id"), u.active)
        uc.update_user(u.user, active=u.active, external_id=u.external_id)
    for email, privs in p.grant.items():
        log.info("granting %s to %s", sorted(privs), email)
        uc.change_metastore_privileges(metastore, email, add=privs, remove=set())
    for email, privs in p.revoke.items():
        log.info("revoking %s from %s", sorted(privs), email)
        uc.change_metastore_privileges(metastore, email, add=set(), remove=privs)
    for u in p.deactivate:
        log.info("deactivating user %s", u.get("id"))
        uc.update_user(u, active=False, external_id=u.get("externalId") or "")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    cfg = load_config(settings.config_path)
    try:
        kc = KeycloakClient(settings.keycloak_issuer_url, settings.keycloak_client_id, settings.keycloak_client_secret)
        uc = UnityCatalogClient(settings.uc_server_url, mint_admin_token(settings.uc_jwt_key_dir))
        sys.exit(run_with_clients(cfg, kc, uc))
    except Exception as e:  # noqa: BLE001 - any failure must fail the Job
        log.error("sync failed: %s", e)
        sys.exit(1)
