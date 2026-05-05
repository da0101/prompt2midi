FROM python:3.10-slim

ARG TORCH_VERSION=2.7.1
ARG TORCHAUDIO_VERSION=2.7.1
ARG ALLIN1_FIX_VERSION=2.0.4

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        ffmpeg \
        git \
        libsndfile1 \
        ninja-build \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

RUN python -m pip install \
        torch==${TORCH_VERSION} \
        torchaudio==${TORCHAUDIO_VERSION} \
        --index-url https://download.pytorch.org/whl/cpu

COPY docker/allin1/patch_natten_cpu.py /tmp/patch_natten_cpu.py

RUN python -m pip install git+https://github.com/CPJKU/madmom \
    && python -m pip install all-in-one-fix==${ALLIN1_FIX_VERSION} --no-build-isolation \
    && python /tmp/patch_natten_cpu.py \
    && allin1fix --help >/dev/null

CMD ["python", "docker/allin1/run_allin1.py", "--help"]
