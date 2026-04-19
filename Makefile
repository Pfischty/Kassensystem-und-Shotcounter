PYTHON := python
PIP := pip

.PHONY: install run test print-doc print-docs print-eventquickstart print-betriebshandbuch print-troubleshooting

install:
	$(PIP) install -r requirements.txt

run:
	flask --app app run --debug

test:
	pytest

print-doc: print-eventquickstart

print-docs: print-eventquickstart print-betriebshandbuch print-troubleshooting

print-eventquickstart:
	mkdir -p output
	pandoc docs/EventQuickstart.md --resource-path=docs --pdf-engine=xelatex -H docs/pandoc_header.tex -o output/EventQuickstart.pdf -V geometry:margin=2cm

print-betriebshandbuch:
	mkdir -p output
	pandoc docs/Betriebshandbuch.md --resource-path=docs --pdf-engine=xelatex -H docs/pandoc_header.tex -o output/Betriebshandbuch.pdf -V geometry:margin=2cm

print-troubleshooting:
	mkdir -p output
	pandoc docs/Troubleshooting.md --resource-path=docs --pdf-engine=xelatex -H docs/pandoc_header.tex -o output/Troubleshooting.pdf -V geometry:margin=2cm
