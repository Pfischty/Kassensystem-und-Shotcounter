PYTHON := python
PIP := pip

.PHONY: install run test

install:
\t$(PIP) install -r requirements.txt

run:
\tflask --app app run --debug

test:
\tpytest
