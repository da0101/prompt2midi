#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-/opt/homebrew/opt/python@3.10/bin/python3.10}"

cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first, then rerun npm run setup:musicgen." >&2
  exit 1
fi

if ! "$PYTHON" --version >/dev/null 2>&1; then
  echo "Python 3.10 not found at $PYTHON. Set PYTHON=/path/to/python3.10 and retry." >&2
  exit 1
fi

uv venv --python "$PYTHON" .venv-audiocraft
uv pip install --python .venv-audiocraft/bin/python -r requirements-audiocraft.txt
uv pip install --python .venv-audiocraft/bin/python audiocraft==1.3.0 --no-deps

XFORMERS_DIR="$ROOT/.venv-audiocraft/lib/python3.10/site-packages/xformers"
mkdir -p "$XFORMERS_DIR"
cat > "$XFORMERS_DIR/__init__.py" <<'PY'
from . import ops

__all__ = ["ops"]
PY
cat > "$XFORMERS_DIR/ops.py" <<'PY'
import torch


class LowerTriangularMask:
    pass


unbind = torch.unbind


def memory_efficient_attention(query, key, value, attn_bias=None, p=0.0, scale=None):
    if isinstance(attn_bias, LowerTriangularMask):
        attn_mask = torch.ones(query.shape[-2], key.shape[-2], device=query.device, dtype=torch.bool).tril()
    else:
        attn_mask = attn_bias
    return torch.nn.functional.scaled_dot_product_attention(
        query,
        key,
        value,
        attn_mask=attn_mask,
        dropout_p=p,
        scale=scale,
    )
PY

echo "AudioCraft MusicGen engine ready at $ROOT/.venv-audiocraft/bin/python"
