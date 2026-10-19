"""Bootstrap training for SpatialCNN via distillation from the heuristic maps (pseudo-labels).

    python -m app.ml.train_spatial_cnn --images /path/to/images --epochs 10

This gives a usable starting model without labels. For production accuracy, replace the
pseudo-labels with real annotations (e.g. AOD / haze masks, NDVI-derived canopy masks).
"""
import argparse
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image

from app.core.config import get_settings
from app.ml.spatial_cnn import INPUT_SIZE, SpatialCNN, heuristic_maps, load_image_tensor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()

    paths = [p for p in Path(args.images).rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}]
    if not paths:
        raise SystemExit("no images found")
    data = torch.cat([load_image_tensor(Image.open(p)) for p in paths])  # (N,3,H,W)
    labels = heuristic_maps(data)
    out_hw = INPUT_SIZE // 8
    y_smog = F.adaptive_avg_pool2d(labels["smog"], out_hw)
    y_can = F.adaptive_avg_pool2d(labels["canopy"], out_hw)

    model = SpatialCNN()
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    n = len(data)
    for epoch in range(args.epochs):
        model.train()
        perm = torch.randperm(n)
        total = 0.0
        for i in range(0, n, args.batch):
            idx = perm[i : i + args.batch]
            out = model(data[idx])
            loss = F.mse_loss(out["smog"], y_smog[idx]) + F.mse_loss(out["canopy"], y_can[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss) * len(idx)
        print(f"epoch {epoch + 1}/{args.epochs} loss={total / n:.5f}")

    out_path = Path(get_settings().artifacts_dir) / "models"
    out_path.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_path / "spatial_cnn.pt")
    print(f"saved {out_path / 'spatial_cnn.pt'}")


if __name__ == "__main__":
    main()
