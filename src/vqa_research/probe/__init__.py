"""Stage 3.5 CLIP probe pilot."""

import os

# Must be set before PyTorch initializes CUDA. This is required by PyTorch for
# deterministic CuBLAS operations on CUDA 10.2 and newer.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
