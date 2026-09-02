from conftest import find, render, render_error

CNPG = {"database": {"cnpg": {"enabled": True}}, "unitycatalog": {"server": {"db": {"type": "postgresql"}}}}


def test_cluster_rendered_with_defaults():
    c = find(render(CNPG), "Cluster", "unity-catalog-db")
    assert c["apiVersion"] == "postgresql.cnpg.io/v1"
    assert c["spec"]["instances"] == 1
    assert c["spec"]["imageName"] == "ghcr.io/cloudnative-pg/postgresql:18.4-system-trixie"
    assert c["spec"]["bootstrap"]["initdb"] == {"database": "unitycatalog", "owner": "unitycatalog"}
    assert c["spec"]["storage"]["size"] == "5Gi"
    assert "storageClass" not in c["spec"]["storage"]
    assert c["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "-1"


def test_storage_class_when_set():
    v = {"database": {"cnpg": {"enabled": True, "storage": {"size": "20Gi", "storageClass": "longhorn"}}},
         "unitycatalog": {"server": {"db": {"type": "postgresql"}}}}
    c = find(render(v), "Cluster", "unity-catalog-db")
    assert c["spec"]["storage"] == {"size": "20Gi", "storageClass": "longhorn"}


def test_server_consumes_cnpg_secret():
    docs = render(CNPG)
    dep = find(docs, "Deployment", "unity-catalog-server")
    init = dep["spec"]["template"]["spec"]["initContainers"][0]
    env = {e["name"]: e for e in init["env"]}
    assert env["DB_PASSWORD"]["valueFrom"]["secretKeyRef"] == {"name": "unity-catalog-db-app", "key": "password"}
    cm = find(docs, "ConfigMap", "unity-catalog-server-config-templates")
    assert "jdbc:postgresql://unity-catalog-db-rw:5432/unitycatalog" in cm["data"]["hibernate.properties.template"]


def test_cnpg_requires_postgresql_mode():
    err = render_error({"database": {"cnpg": {"enabled": True}}})
    assert "unitycatalog.server.db.type must be postgresql" in err
