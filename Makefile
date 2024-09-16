SRC_DIR ?= ./src
MYPY_DIRS := $(shell find ${SRC_DIR}/package ! -path '*.egg-info*' -type d -maxdepth 1 -mindepth 1 | xargs)

.PHONY: lint
lint:
	ruff check --target-version=py311 ${SRC_DIR}

.PHONY: lint-github
lint-github:
	ruff check --output-format=github --target-version=py311 ${SRC_DIR}

.PHONY: mypy
mypy: $(MYPY_DIRS)
	$(foreach d, $(MYPY_DIRS), python -m mypy $(d);)

.PHONY: test
test:
	pytest --cov=motu_server -v -s ${SRC_DIR}/tests

.PHONY: develop
develop:
	python -m pip install --editable ${SRC_DIR}
	python -m pip install -U -r requirements-dev.txt

.PHONY: install
install:
	python -m pip install -U -r requirements.txt

.PHONY: run
run: install
	./run --datastore ./datastore.json --port 8888

.PHONY: build-pypi
build-pypi:
	python -m build ${SRC_DIR}

.PHONY: deploy-pypi-test
deploy-pypi-test:
	twine upload --repository motu_server_test ${SRC_DIR}/dist/* 

.PHONY: deploy-pypi
deploy-pypi-test:
	twine upload --repository motu_server ${SRC_DIR}/dist/* 

.PHONY: build-gcloud
build-gcloud:
	gcloud builds submit \
		--tag gcr.io/motu-avb-controller/motu-server

.PHONY: deploy-gcloud
deploy-gcloud:
	gcloud run deploy motu-server \
		--image gcr.io/motu-avb-controller/motu-server \
		--platform managed \
		--region us-central1 \
		--allow-unauthenticated