# Local development Makefile for the Unity Catalog pack.
#
# Standalone (no Nebari stack):
#   make up-standalone   kind cluster + chart with H2 and no auth
#   make smoke           curl the API through the UI proxy
# Nebari (MetalLB, Envoy Gateway, cert-manager, Keycloak, nebari-operator, CNPG):
#   make up-nebari
#   make update-hosts    add the NebariApp hostname to /etc/hosts
#   make down            delete the kind cluster
#
# Prerequisites: docker, kind, helm, kubectl, git

CHART         := ../chart
CLUSTER_NAME  := unity-catalog-dev
HOSTNAME      := uc.nebari.local
CACHE_DIR     := .cache
OPERATOR_REPO := $(CACHE_DIR)/nebari-operator
OPERATOR_REF  := v0.1.0-alpha.19

define METALLB_POOL
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: kind-pool
  namespace: metallb-system
spec:
  addresses:
  - METALLB_BASE_IP.255.200-METALLB_BASE_IP.255.250
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: kind-l2
  namespace: metallb-system
spec:
  ipAddressPools:
  - kind-pool
endef
export METALLB_POOL

.PHONY: cluster up-standalone up-nebari smoke update-hosts down _ui-image _sync-image _cnpg

# --------------------------------------------------------------------------
# Nebari infrastructure on kind (mirrors software-pack-template/dev/Makefile)
# --------------------------------------------------------------------------
cluster:
	@if kind get clusters 2>/dev/null | grep -q "^$(CLUSTER_NAME)$$"; then \
		echo "Cluster '$(CLUSTER_NAME)' already exists, skipping setup"; \
	else \
		$(MAKE) _cluster-create; \
	fi

_cluster-create: _clone-operator _kind-create _metallb _services _keycloak-setup _operator _label-namespace
	@echo "Cluster setup complete."

_clone-operator:
	@if [ ! -d "$(OPERATOR_REPO)" ]; then \
		mkdir -p $(CACHE_DIR); \
		git clone --depth 1 --branch $(OPERATOR_REF) \
			https://github.com/nebari-dev/nebari-operator.git $(OPERATOR_REPO); \
	fi

_kind-create:
	kind create cluster --name $(CLUSTER_NAME)

_metallb:
	kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml 2>&1 | grep -v "unrecognized format"
	kubectl wait --namespace metallb-system --for=condition=available deployment/controller --timeout=90s
	kubectl wait --namespace metallb-system --for=jsonpath='{.status.numberReady}'=1 daemonset/speaker --timeout=90s
	@KIND_NET_CIDR=$$(docker network inspect kind -f '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}' 2>/dev/null | grep '\.' | head -n1); \
	BASE_IP=$$(echo $${KIND_NET_CIDR} | awk -F. '{print $$1"."$$2}'); \
	echo "$$METALLB_POOL" | sed "s/METALLB_BASE_IP/$${BASE_IP}/g" | kubectl apply -f -

_services:
	CLUSTER_NAME=$(CLUSTER_NAME) $(OPERATOR_REPO)/dev/scripts/services/install.sh

_keycloak-setup:
	CLUSTER_NAME=$(CLUSTER_NAME) $(OPERATOR_REPO)/dev/scripts/services/keycloak/setup.sh

_operator:
	kubectl apply -f https://github.com/nebari-dev/nebari-operator/releases/download/$(OPERATOR_REF)/install.yaml
	kubectl wait --for=condition=available deployment/nebari-operator-controller-manager \
		-n nebari-operator-system --timeout=120s

_label-namespace:
	kubectl create namespace unity-catalog --dry-run=client -o yaml | kubectl apply -f -
	kubectl label namespace unity-catalog nebari.dev/managed=true --overwrite

_cnpg:
	helm repo add cnpg https://cloudnative-pg.github.io/charts >/dev/null
	helm upgrade --install cloudnative-pg cnpg/cloudnative-pg -n cnpg-system --create-namespace --wait

# --------------------------------------------------------------------------
# Images (built locally and loaded into kind)
# --------------------------------------------------------------------------
_ui-image:
	docker build -t unity-catalog-ui:dev ../images/ui
	kind load docker-image unity-catalog-ui:dev --name $(CLUSTER_NAME)

_sync-image:
	docker build -t unity-catalog-keycloak-sync:dev ../images/sync
	kind load docker-image unity-catalog-keycloak-sync:dev --name $(CLUSTER_NAME)

# --------------------------------------------------------------------------
# Standalone: plain kind cluster, H2, no auth
# --------------------------------------------------------------------------
up-standalone:
	@kind get clusters 2>/dev/null | grep -q "^$(CLUSTER_NAME)$$" || kind create cluster --name $(CLUSTER_NAME)
	$(MAKE) _ui-image
	helm upgrade --install unity-catalog $(CHART) -n unity-catalog --create-namespace \
		-f ../examples/standalone-values.yaml \
		--set unitycatalog.ui.deployment.image.repository=unity-catalog-ui \
		--set unitycatalog.ui.deployment.image.tag=dev \
		--set unitycatalog.ui.deployment.image.pullPolicy=Never \
		--wait --timeout 8m
	@echo "kubectl -n unity-catalog port-forward svc/unity-catalog-ui 3000:3000 ; open http://localhost:3000"

smoke:
	kubectl -n unity-catalog port-forward svc/unity-catalog-ui 3000:3000 & sleep 4; \
	curl -fsS localhost:3000/config.js && curl -fsS localhost:3000/api/2.1/unity-catalog/catalogs && echo; kill %1

# --------------------------------------------------------------------------
# Nebari: full stack plus CNPG. Group sync stays off unless you create the
# Keycloak service-account Secret (docs/keycloak-service-account.md).
# --------------------------------------------------------------------------
up-nebari: cluster _cnpg _ui-image _sync-image
	helm upgrade --install unity-catalog $(CHART) -n unity-catalog \
		-f ../examples/nebari-values.yaml \
		--set nebariapp.hostname=$(HOSTNAME) \
		--set sync.enabled=false \
		--set unitycatalog.ui.deployment.image.repository=unity-catalog-ui \
		--set unitycatalog.ui.deployment.image.tag=dev \
		--set unitycatalog.ui.deployment.image.pullPolicy=Never \
		--wait --timeout 10m
	kubectl wait --for=condition=Ready nebariapp/unity-catalog -n unity-catalog --timeout=180s
	CLUSTER_NAME=$(CLUSTER_NAME) $(OPERATOR_REPO)/dev/scripts/networking/update-hosts.sh
	@echo "https://$(HOSTNAME)  (Keycloak: admin / nebari-admin; the user must also exist in UC, see docs)"

update-hosts:
	CLUSTER_NAME=$(CLUSTER_NAME) $(OPERATOR_REPO)/dev/scripts/networking/update-hosts.sh

down:
	kind delete cluster --name $(CLUSTER_NAME)
