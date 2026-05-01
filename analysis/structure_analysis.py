#!/usr/bin/env python3
"""Track structure analysis: section detection, energy arc, arrangement summary."""
from __future__ import annotations

import os

_FALLBACK = {
    "sections": [],
    "section_count": 0,
    "estimated_bars": 0,
    "arrangement_arc": "unknown",
    "energy_profile": "unknown",
    "method": "disabled",
}


def analyze_structure(audio_path: str, bpm: float) -> dict:
    """Detect track sections, energy arc, and arrangement summary using librosa."""
    if os.environ.get("PROMPT2MIDI_DISABLE_STRUCTURE") == "1":
        return _FALLBACK.copy()
    if not audio_path or not os.path.exists(audio_path):
        return _FALLBACK.copy()

    try:
        import librosa
        import numpy as np
        from scipy.linalg import eigh
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import pdist

        y, sr = librosa.load(audio_path, sr=22050, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        hop = 512
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=4, hop_length=hop)
        rms = librosa.feature.rms(y=y, hop_length=hop)

        # Stack and normalize features
        features = np.vstack([chroma, mfcc, rms])
        features = features / (np.linalg.norm(features, axis=0, keepdims=True) + 1e-8)

        # Downsample to ~0.5s blocks for tractable segmentation
        block_frames = max(1, int(0.5 * sr / hop))
        n_frames = features.shape[1]
        n_blocks = max(4, n_frames // block_frames)
        blocks = np.array([
            features[:, i * block_frames: (i + 1) * block_frames].mean(axis=1)
            for i in range(n_blocks)
        ])

        # Laplacian segmentation
        k = min(8, n_blocks // 2)
        try:
            from scipy.sparse.csgraph import laplacian as csgraph_laplacian
            affinity = blocks @ blocks.T
            affinity = np.clip(affinity, 0, None)
            L = csgraph_laplacian(affinity, normed=True)
            _, vecs = eigh(L, subset_by_index=[0, k - 1])
            boundaries_frames = librosa.segment.agglomerative(vecs.T, k=k)
        except Exception:
            boundaries_frames = librosa.segment.agglomerative(blocks.T, k=k)

        boundaries_sec = [b * block_frames * hop / sr for b in boundaries_frames]
        boundaries_sec = sorted(set([0.0] + boundaries_sec + [duration]))

        # Compute per-section energy
        rms_times = librosa.frames_to_time(np.arange(rms.shape[1]), sr=sr, hop_length=hop)
        sections = []
        for i in range(len(boundaries_sec) - 1):
            t0, t1 = boundaries_sec[i], boundaries_sec[i + 1]
            mask = (rms_times >= t0) & (rms_times < t1)
            energy = float(rms[0, mask].mean()) if mask.any() else 0.0
            sections.append({"start": round(t0, 2), "end": round(t1, 2), "energy": round(energy, 4)})

        # Label sections A/B/C… by clustering feature similarity
        section_feats = np.array([
            blocks[min(int(s["start"] / (block_frames * hop / sr)), n_blocks - 1)]
            for s in sections
        ])
        if len(sections) > 2:
            dists = pdist(section_feats, metric="cosine")
            Z = linkage(dists, method="ward")
            cluster_ids = fcluster(Z, t=min(4, len(sections) // 2), criterion="maxclust")
            label_map: dict[int, str] = {}
            for cid in cluster_ids:
                if cid not in label_map:
                    label_map[cid] = chr(65 + len(label_map))
            for s, cid in zip(sections, cluster_ids):
                s["label"] = label_map[cid]
        else:
            for i, s in enumerate(sections):
                s["label"] = chr(65 + i)

        energies = [s["energy"] for s in sections]
        arrangement_arc = _infer_arc(energies)
        first_e, last_e = energies[0] if energies else 0, energies[-1] if energies else 0
        energy_profile = f"{_level(first_e)} → {_level(last_e)}" if energies else "unknown"
        estimated_bars = max(0, round(duration * bpm / 60 / 4))

        return {
            "sections": sections,
            "section_count": len(sections),
            "estimated_bars": estimated_bars,
            "arrangement_arc": arrangement_arc,
            "energy_profile": energy_profile,
            "method": "laplacian_segmentation",
        }
    except Exception:
        return _FALLBACK.copy()


def _infer_arc(energies: list[float]) -> str:
    if not energies or len(energies) < 2:
        return "unknown"
    span = max(energies) - min(energies)
    if span < 0.05:
        return "steady throughout"
    first_half = energies[: len(energies) // 2]
    second_half = energies[len(energies) // 2 :]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    if avg_second > avg_first * 1.1:
        return "builds over time"
    if avg_second < avg_first * 0.9:
        return "drops over time"
    peak_idx = energies.index(max(energies))
    if 0 < peak_idx < len(energies) - 1:
        return "builds then drops"
    return "steady throughout"


def _level(e: float) -> str:
    if e > 0.15:
        return "high"
    if e > 0.06:
        return "medium"
    return "low"
