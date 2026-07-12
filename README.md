# 3DGS-Survey-Paper

LaTeX source for: **3D Gaussian Splatting: A Comprehensive Taxonomy and Benchmark Survey**

## Build

```bash
make            # compile PDF (pdflatex + bibtex)
make clean      # remove auxiliary files
make cleanall   # remove all generated files including PDF
make view       # compile and open PDF (macOS)
```

Or manually:
```bash
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

## Repository Structure

```
3DGS-Survey-Paper/
├── main.tex                 # Main LaTeX file
├── references.bib           # BibTeX references
├── sections/                # Per-section .tex files
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── related_work.tex
│   ├── taxonomy.tex
│   ├── benchmark.tex
│   ├── analysis.tex
│   └── conclusion.tex
├── figures/                 # All paper figures (PDF/EPS)
├── supplementary/           # Supplementary material
├── .gitignore               # Ignores LaTeX build artifacts
├── Makefile                 # Build automation
├── CITATION.cff             # Citation metadata
└── LICENSE                  # CC-BY-4.0
```

## Related Repositories

| Repository | Description |
|------------|-------------|
| [3DGS-Survey](https://github.com/autumn119/3DGS-Survey) | Project page (GitHub Pages) |
| [3DGS-Survey-Taxonomy-Benchmark](https://github.com/autumn119/3DGS-Survey-Taxonomy-Benchmark) | Benchmark code & data |

## Citation

```bibtex
@article{tao2026_3dgs_survey,
  author  = {Tao, Jiaxing},
  title   = {3D Gaussian Splatting: A Comprehensive Taxonomy and Benchmark Survey},
  journal = {IEEE Transactions on Visualization and Computer Graphics},
  year    = {2026},
  doi     = {10.5281/zenodo.20263999}
}
```

## License

This work is licensed under **CC-BY-4.0**. See [LICENSE](LICENSE) for details.
