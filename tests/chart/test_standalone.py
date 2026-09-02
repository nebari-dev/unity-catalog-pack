from conftest import find, find_all


def test_server_and_ui_deployments_use_fullname_override(standalone_docs):
    assert find(standalone_docs, "Deployment", "unity-catalog-server") is not None
    assert find(standalone_docs, "Deployment", "unity-catalog-ui") is not None
    assert find(standalone_docs, "Service", "unity-catalog-ui")["spec"]["ports"][0]["port"] == 3000


def test_standalone_has_no_nebari_resources(standalone_docs):
    assert find_all(standalone_docs, "NebariApp") == []
    assert find_all(standalone_docs, "Cluster") == []
    assert find_all(standalone_docs, "CronJob") == []
    assert find_all(standalone_docs, "HTTPRoute") == []
    assert find_all(standalone_docs, "Ingress") == []


def test_standalone_uses_h2_with_pvc(standalone_docs):
    assert find(standalone_docs, "PersistentVolumeClaim", "unity-catalog-server-db") is not None
    cm = find(standalone_docs, "ConfigMap", "unity-catalog-server-config-templates")
    assert "org.h2.Driver" in cm["data"]["hibernate.properties.template"]


def test_server_image_is_pinned_release(standalone_docs):
    dep = find(standalone_docs, "Deployment", "unity-catalog-server")
    images = [c["image"] for c in dep["spec"]["template"]["spec"]["containers"]]
    assert "unitycatalog/unitycatalog:v0.6.0" in images


def test_ui_image_is_first_party(standalone_docs):
    dep = find(standalone_docs, "Deployment", "unity-catalog-ui")
    ui = dep["spec"]["template"]["spec"]["containers"][0]
    assert ui["image"].startswith("quay.io/nebari/unity-catalog-pack-unity-catalog-ui:")
