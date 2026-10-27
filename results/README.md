# Benchmark Results

This directory holds the quantitative outputs of the benchmark. The manuscript
source is not included in this repository (under review); the tables below can be
regenerated from the scripts in `code/`.

## Layout

```
results/
├── rendering_benchmark.csv     # Per-scene × per-method PSNR / SSIM / LPIPS (test views)
├── training_efficiency.csv     # Training time & peak memory per scene × method
├── rendering_speed.csv         # FPS at target resolution
├── geometric_consistency.csv   # Acc / Recall / F1 / NCD / P95 vs. SfM-MVS reference (tower body)
└── dark_region_coverage.csv    # Dark/lit coverage ratio & dark-region PSNR (ground-level views)
```

## Regenerating

```bash
# Rendering metrics (PSNR / SSIM / LPIPS) for all scenes & methods
python code/eval/metrics.py --scene all --method all
# -> writes <OUTPUT_ROOT>/results_summary.csv ; copy here as rendering_benchmark.csv
```

## Column conventions

- `scene` ∈ {chaoli, congjiang, zeli, zengchong}
- `method` ∈ {mvs, nerf, 2dgs, 3dgs, ingp}
- Metrics computed on held-out test views (LLFF-style split, every 8th frame).
- Geometric consistency is evaluated on uniformly cropped tower bodies (MeshLab)
  against the SfM-MVS fused mesh as reference.
