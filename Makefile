.PHONY: install dev_install upgrade_dependencies

install:
	pip install -r ./requirements/common.txt

dev_install: install
	pip install -r ./requirements/develop.txt

upgrade_dependencies:
	pip install pip-tools
	pip-compile --upgrade --output-file ./requirements/common.txt ./requirements/common.in
	pip-compile --upgrade --output-file ./requirements/develop.txt ./requirements/develop.in
	pip-compile --upgrade --output-file ./requirements/workers.txt ./requirements/workers.in
