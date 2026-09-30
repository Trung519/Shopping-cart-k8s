SHELL := /bin/bash
ENV_FILE := $(if $(wildcard .env.local),.env.local,.env.example)
TARGET_HOST_IP ?= $(shell docker run --rm alpine:3.22 getent hosts host.docker.internal 2>/dev/null | awk 'NR == 1 {print $$1}')
COMPOSE := TARGET_HOST_IP=$(TARGET_HOST_IP) docker compose --env-file $(ENV_FILE)
BASE_URL ?= http://shopping-cart.localhost:8080
KUBE_CONTEXT ?= k3d-lab-k8s
VUS ?= 200
RUN_ID ?= $(shell date +%Y%m%d-%H%M%S)
SEED ?= 20260802

.PHONY: up down status configure prepare preflight smoke load stress cleanup monitor report validate unit k6-run verify-run self-test-failure

up: configure
	$(COMPOSE) up -d prometheus grafana cluster-monitor

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

configure:
	mkdir -p .local/fixtures .local/results
	kubectl config view --raw --minify --context $(KUBE_CONTEXT) --flatten | sed -E 's#server: https://(0\.0\.0\.0|127\.0\.0\.1|localhost):#server: https://host.docker.internal:#' | awk '/certificate-authority-data:/ {next} {print} /server: https:\/\/host\.docker\.internal:/ {print "    insecure-skip-tls-verify: true"}' > .local/kubeconfig
	chmod 600 .local/kubeconfig

preflight: configure
	$(COMPOSE) run --rm performance-tools /work/scripts/preflight.sh

prepare: preflight
	security find-generic-password -a $(KUBE_CONTEXT) -s shopping-cart-marketplace-admin -w | $(COMPOSE) run --rm -T -e RUN_ID=$(RUN_ID) -e VUS=$(VUS) -e PROFILE=$(PROFILE) -e SEED=$(SEED) performance-tools /work/scripts/prepare.sh --admin-password-stdin

monitor:
	$(COMPOSE) run --rm -e RUN_ID=$(RUN_ID) performance-tools /work/scripts/monitor-cluster.sh

smoke:
	RUN_ID=$(RUN_ID) SEED=$(SEED) ./scripts/run-test.sh smoke 5

load:
	RUN_ID=$(RUN_ID) SEED=$(SEED) ./scripts/run-test.sh load-200 200

stress:
	@test "$(CONFIRM)" = "I_UNDERSTAND" || (echo "Use: make stress CONFIRM=I_UNDERSTAND" && exit 2)
	RUN_ID=$(RUN_ID) SEED=$(SEED) ./scripts/run-test.sh stress-500 500

k6-run:
	$(COMPOSE) run --rm -e RUN_ID=$(RUN_ID) -e PROFILE=$(PROFILE) -e FIXTURE_FILE=/work/.local/fixtures/$(RUN_ID).json k6 run --summary-export=/work/.local/results/$(RUN_ID)/summary.json /work/scenarios/shopcart.js

verify-run:
	$(COMPOSE) run --rm -e RUN_ID=$(RUN_ID) -e PROFILE=$(PROFILE) performance-tools /work/scripts/verify-run.sh

self-test-failure:
	@if RUN_ID=$(RUN_ID) SEED=$(SEED) ./scripts/run-test.sh self-fail 5; then echo "Expected threshold failure but run passed"; exit 1; fi
	@grep -q 'Status:.*`FAILED`' .local/results/$(RUN_ID)/report.md
	@test "$$(cat .local/results/$(RUN_ID)/cleanup.exit)" = "0"

cleanup: configure
	security find-generic-password -a $(KUBE_CONTEXT) -s shopping-cart-marketplace-admin -w | $(COMPOSE) run --rm -T -e RUN_ID=$(RUN_ID) performance-tools /work/scripts/cleanup.sh --admin-password-stdin

report:
	$(COMPOSE) run --rm -e RUN_ID=$(RUN_ID) -e PROFILE=$(PROFILE) performance-tools /work/scripts/report.sh

validate:
	$(COMPOSE) config --quiet
	python3 -m json.tool profiles/smoke.json >/dev/null
	python3 -m json.tool profiles/load-200.json >/dev/null
	python3 -m json.tool profiles/stress-500.json >/dev/null
	python3 -m json.tool profiles/payment-api.json >/dev/null
	python3 -m json.tool profiles/self-fail.json >/dev/null
	python3 -m json.tool config/test-data.json >/dev/null

unit:
	bash -n scripts/*.sh
	docker run --rm -v $(CURDIR):/work -w /work node:22-alpine npm test
	$(COMPOSE) config --quiet
