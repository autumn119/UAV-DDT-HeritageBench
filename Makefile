# ============================================================
# Makefile — 3DGS Survey 论文编译脚本
# 用法:
#   make            编译论文 (pdflatex + bibtex + pdflatex×2)
#   make clean      清理编译产物
#   make cleanall   深度清理 (含 PDF)
#   make view       编译并打开 PDF (macOS)
# ============================================================

TEX      = main
LATEX    = pdflatex
BIBTEX   = bibtex
VIEWER   = open    # macOS: open / Windows: start / Linux: xdg-open

.PHONY: all clean cleanall view

all: $(TEX).pdf

$(TEX).pdf: $(TEX).tex
	$(LATEX) -interaction=nonstopmode $(TEX)
	$(BIBTEX) $(TEX)
	$(LATEX) -interaction=nonstopmode $(TEX)
	$(LATEX) -interaction=nonstopmode $(TEX)

view: $(TEX).pdf
	$(VIEWER) $(TEX).pdf

clean:
	rm -f *.aux *.log *.out *.bbl *.blg *.synctex.gz
	rm -f *.fls *.fdb_latexmk *.toc *.lof *.lot
	rm -f *.nav *.snm *.vrb *.idx *.ilg *.ind
	rm -f *.bcf *.run.xml *.xml *.xdv *.dvi

cleanall: clean
	rm -f *.pdf
