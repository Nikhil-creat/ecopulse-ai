"""Spatial CNN for satellite / aerial / thermal imagery.

Fully-convolutional ResNet-style network with two dense heads producing per-cell maps:
  * smog map   -> Smog Severity Index (0-100)
  * canopy map -> Urban Green Canopy Density (0-1)
The same maps are pooled to a grid for the 3D heatmap layer.

If no trained weights exist at <artifacts>/models/spatial_cnn.pt the analyzer falls back to
physics/colour heuristics (dark-channel haze prior + Excess-Green index) and reports
model_source="heuristic" so downstream consumers know. Train weights with
`python -m app.ml.train_spatial_cnn` (see that file).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

MODEL_VERSION = "spatial-cnn-0.1"
INPUT_SIZE = 256
GRID = 16


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, stride: int = 1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(c_in, c_out, 3, stride, 1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ResBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, stride: int = 1) -> None:
        super().__init__()
        self.conv1 = ConvBlock(c_in, c_out, stride)
        self.conv2 = nn.Sequential(nn.Conv2d(c_out, c_out, 3, 1, 1, bias=False), nn.BatchNorm2d(c_out))
        self.skip = (
            nn.Identity() if stride == 1 and c_in == c_out
            else nn.Sequential(nn.Conv2d(c_in, c_out, 1, stride, bias=False), nn.BatchNorm2d(c_out))
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.relu(self.conv2(self.conv1(x)) + self.skip(x))


class SpatialCNN(nn.Module):
    """Output stride 8: a 256x256 input yields 32x32 maps."""

    def __init__(self, in_ch: int = 3, width: int = 32) -> None:
        super().__init__()
        w = width
        self.backbone = nn.Sequential(
            ConvBlock(in_ch, w, stride=2),
            ResBlock(w, w),
            ResBlock(w, 2 * w, stride=2),
            ResBlock(2 * w, 4 * w, stride=2),
            ResBlock(4 * w, 4 * w),
        )
        self.smog_head = nn.Conv2d(4 * w, 1, 1)
        self.canopy_head = nn.Conv2d(4 * w, 1, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        f = self.backbone(x)
        return {"smog": torch.sigmoid(self.smog_head(f)), "canopy": torch.sigmoid(self.canopy_head(f))}


# ----------------------------- heuristics (fallback + pseudo-labels) -----------------------------
def heuristic_maps(x: torch.Tensor) -> dict[str, torch.Tensor]:
    """x: (B,3,H,W) in [0,1]. Returns per-pixel smog and canopy maps in [0,1], shape (B,1,H,W)."""
    dark = -F.max_pool2d(-x.min(dim=1, keepdim=True).values, 15, 1, 7)  # dark channel prior
    gray = x.mean(dim=1, keepdim=True)
    local_mean = F.avg_pool2d(gray, 9, 1, 4)
    local_std = (F.avg_pool2d(gray**2, 9, 1, 4) - local_mean**2).clamp_min(0).sqrt()
    low_contrast = 1.0 - (local_std * 6).clamp(0, 1)
    smog = (0.7 * dark + 0.3 * low_contrast).clamp(0, 1)

    r, g, b = x[:, 0:1], x[:, 1:2], x[:, 2:3]
    exg = 2 * g - r - b
    canopy = torch.sigmoid((exg - 0.05) * 20)
    return {"smog": smog, "canopy": canopy}


# ----------------------------- analyzer -----------------------------
@dataclass
class SpatialResult:
    smog_severity_index: float
    green_canopy_density: float
    heatmap: dict[str, Any]
    model_version: str
    model_source: str  # "cnn" | "heuristic"


def load_image_tensor(img: Image.Image, size: int = INPUT_SIZE) -> torch.Tensor:
    arr = np.asarray(img.convert("RGB").resize((size, size), Image.BILINEAR), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)


class SpatialAnalyzer:
    def __init__(self, weights_path: str | Path | None = None, device: str = "cpu") -> None:
        self.device = torch.device(device)
        self.model: SpatialCNN | None = None
        if weights_path and Path(weights_path).is_file():
            model = SpatialCNN()
            model.load_state_dict(torch.load(weights_path, map_location=self.device))
            self.model = model.to(self.device).eval()

    @torch.inference_mode()
    def analyze(self, img: Image.Image) -> SpatialResult:
        x = load_image_tensor(img).to(self.device)
        maps = self.model(x) if self.model else heuristic_maps(x)
        smog, canopy = maps["smog"], maps["canopy"]
        grid = lambda t: F.adaptive_avg_pool2d(t, GRID)[0, 0].cpu().numpy().round(3).tolist()  # noqa: E731
        return SpatialResult(
            smog_severity_index=round(float(smog.mean()) * 100, 2),
            green_canopy_density=round(float(canopy.mean()), 4),
            heatmap={"grid": GRID, "smog": grid(smog), "canopy": grid(canopy)},
            model_version=MODEL_VERSION,
            model_source="cnn" if self.model else "heuristic",
        )
