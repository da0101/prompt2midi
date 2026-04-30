#!/usr/bin/env python3
"""Reference groove fingerprinting for generation conditioning."""
from __future__ import annotations

import math
import os
import json
import subprocess
import sys
import tempfile

_FALLBACK = {
    "method": "unavailable",
    "kick_pattern_16th": [],
    "bass_accent_pattern_16th": [],
    "hat_pattern_16th": [],
    "bass_motif_16th": [],
    "bass_notes": [],
    "swing": 0.0,
    "low_end_weight": "medium",
    "drum_feel": "steady",
    "bass_feel": "rolling",
    "club_energy": "medium",
    "prompt": "",
    "warnings": ["Reference groove analysis unavailable."],
}

_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def analyze_reference_groove(audio_path: str, bpm: float | None, section: dict | None = None) -> dict:
    """Analyze the full reference for kick, bass, swing, and low-end feel."""
    if os.environ.get("PROMPT2MIDI_DISABLE_REFERENCE_GROOVE") == "1":
        return dict(_FALLBACK)
    if not audio_path or not os.path.exists(audio_path):
        return dict(_FALLBACK)
    if _should_skip_unsafe_groove():
        fallback = dict(_FALLBACK)
        fallback["warnings"] = [
            "Reference groove analysis skipped because the local macOS Python 3.14 librosa/numba stack can segfault. "
            "Set PROMPT2MIDI_ENABLE_UNSAFE_REFERENCE_GROOVE=1 to opt in."
        ]
        return fallback
    if os.environ.get("PROMPT2MIDI_REFERENCE_GROOVE_CHILD") != "1":
        return _analyze_reference_groove_subprocess(audio_path, bpm, section)

    return _analyze_reference_groove_unsafe(audio_path, bpm, section)


def _analyze_reference_groove_subprocess(audio_path: str, bpm: float | None, section: dict | None = None) -> dict:
    env = dict(os.environ)
    env["PROMPT2MIDI_REFERENCE_GROOVE_CHILD"] = "1"
    env.setdefault("NUMBA_CACHE_DIR", _numba_cache_dir())
    command = [
        sys.executable,
        os.path.abspath(__file__),
        "--json",
        audio_path,
        "--bpm",
        str(_coerce_bpm(bpm)),
    ]
    start_seconds = (section or {}).get("start_seconds")
    if start_seconds is not None:
        command.extend(["--section-start", str(start_seconds)])

    try:
        completed = subprocess.run(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=float(os.environ.get("PROMPT2MIDI_REFERENCE_GROOVE_TIMEOUT") or "45"),
            check=False,
        )
    except Exception as exc:
        fallback = dict(_FALLBACK)
        fallback["warnings"] = [f"Reference groove analysis failed in isolated process: {exc}"]
        return fallback

    if completed.returncode != 0:
        fallback = dict(_FALLBACK)
        detail = (completed.stderr or completed.stdout or f"exit code {completed.returncode}").strip()
        fallback["warnings"] = [f"Reference groove analysis crashed or failed in isolated process: {detail[:300]}"]
        return fallback

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fallback = dict(_FALLBACK)
        fallback["warnings"] = [f"Reference groove analysis returned invalid JSON: {exc}"]
        return fallback
    return payload if isinstance(payload, dict) else dict(_FALLBACK)


def _analyze_reference_groove_unsafe(audio_path: str, bpm: float | None, section: dict | None = None) -> dict:
    """Run librosa/numba groove extraction.

    This can segfault on some Python 3.14/macOS builds, so callers should use
    analyze_reference_groove(), which isolates this code in a child process.
    """

    try:
        _ensure_numba_cache()
        import librosa
        import numpy as np
        from scipy.signal import butter, sosfilt

        sr = 22050
        y, _ = librosa.load(audio_path, sr=sr, mono=True)
        if y.size < sr * 4:
            return dict(_FALLBACK)
        duration_seconds = y.size / float(sr)

        tempo = _coerce_bpm(bpm)
        sixteenth = 60.0 / tempo / 4.0
        low = _bandpass(y, sr, 28.0, 180.0)
        kick_band = _bandpass(y, sr, 35.0, 130.0)
        bass_band = _bandpass(y, sr, 45.0, 260.0)
        hat_band = _bandpass(y, sr, 2500.0, 9000.0)

        kick_times = librosa.onset.onset_detect(y=kick_band, sr=sr, units="time", delta=0.055, wait=2)
        bass_times = librosa.onset.onset_detect(y=bass_band, sr=sr, units="time", delta=0.04, wait=1)
        hat_times = librosa.onset.onset_detect(y=hat_band, sr=sr, units="time", delta=0.045, wait=1)

        kick_pattern = _dominant_pattern(kick_times, sixteenth, bars=2)
        bass_pattern = _dominant_pattern(bass_times, sixteenth, bars=2)
        hat_pattern = _dominant_pattern(hat_times, sixteenth, bars=2)
        swing = _estimate_swing(hat_times, sixteenth)
        low_end_weight = _low_end_weight(y, low)
        drum_feel = _drum_feel(kick_pattern)
        bass_feel = _bass_feel(bass_pattern)
        club_energy = _club_energy(y, low, kick_pattern, bass_pattern)
        if duration_seconds >= 20.0:
            bass_notes = _bass_notes(librosa, np, bass_band, sr, tempo)
            bass_motif = _bass_motif_16th(librosa, np, bass_band, sr, tempo, sixteenth, bass_pattern)
        else:
            bass_notes = []
            bass_motif = []

        prompt = _build_prompt(
            kick_pattern=kick_pattern,
            bass_pattern=bass_pattern,
            hat_pattern=hat_pattern,
            bass_motif=bass_motif,
            bass_notes=bass_notes,
            swing=swing,
            low_end_weight=low_end_weight,
            drum_feel=drum_feel,
            bass_feel=bass_feel,
            club_energy=club_energy,
        )
        return {
            "method": "full_track_low_end_onset_fingerprint",
            "kick_pattern_16th": kick_pattern,
            "bass_accent_pattern_16th": bass_pattern,
            "hat_pattern_16th": hat_pattern,
            "bass_motif_16th": bass_motif,
            "bass_notes": bass_notes,
            "swing": round(swing, 3),
            "low_end_weight": low_end_weight,
            "drum_feel": drum_feel,
            "bass_feel": bass_feel,
            "club_energy": club_energy,
            "prompt": prompt,
            "section_start_seconds": (section or {}).get("start_seconds"),
            "warnings": [
                "Groove fingerprint is derived from full-mix low-frequency/transient analysis; it is not a copyrighted melody copy."
            ],
        }
    except Exception as exc:
        fallback = dict(_FALLBACK)
        fallback["warnings"] = [f"Reference groove analysis failed: {exc}"]
        return fallback


def _ensure_numba_cache() -> None:
    if os.environ.get("NUMBA_CACHE_DIR"):
        return
    cache_dir = _numba_cache_dir()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["NUMBA_CACHE_DIR"] = cache_dir
    except OSError:
        pass


def _numba_cache_dir() -> str:
    return os.path.join(tempfile.gettempdir(), "prompt2midi-numba-cache")


def _should_skip_unsafe_groove() -> bool:
    if os.environ.get("PROMPT2MIDI_ENABLE_UNSAFE_REFERENCE_GROOVE") == "1":
        return False
    return sys.platform == "darwin" and sys.version_info >= (3, 14)


def _coerce_bpm(bpm: float | None) -> float:
    try:
        value = float(bpm or 124.0)
    except (TypeError, ValueError):
        value = 124.0
    return max(80.0, min(150.0, value))


def _bandpass(y, sr: int, low: float, high: float):
    from scipy.signal import butter, sosfilt

    nyq = sr / 2.0
    low_norm = max(0.001, low / nyq)
    high_norm = min(0.999, high / nyq)
    sos = butter(4, [low_norm, high_norm], btype="band", output="sos")
    return sosfilt(sos, y)


def _dominant_pattern(times, sixteenth: float, bars: int = 2) -> list[int]:
    steps = 16 * bars
    if len(times) == 0:
        return []
    counts = [0] * steps
    for value in times:
        index = int(round(float(value) / sixteenth)) % steps
        counts[index] += 1
    if max(counts) <= 0:
        return []
    threshold = max(2, math.ceil(max(counts) * 0.32))
    positions = [index for index, count in enumerate(counts) if count >= threshold]
    if len(positions) > 12:
        ranked = sorted(range(steps), key=lambda index: counts[index], reverse=True)[:12]
        positions = sorted(ranked)
    return positions


def _estimate_swing(hat_times, sixteenth: float) -> float:
    if len(hat_times) < 8:
        return 0.0
    deviations: list[float] = []
    for value in hat_times:
        grid = round(float(value) / sixteenth)
        if grid % 2 == 1:
            expected = grid * sixteenth
            deviations.append((float(value) - expected) / sixteenth)
    if not deviations:
        return 0.0
    return max(0.0, min(0.33, sum(deviations) / len(deviations)))


def _low_end_weight(y, low) -> str:
    import numpy as np

    full_rms = float(np.sqrt(np.mean(np.square(y))) or 1e-9)
    low_rms = float(np.sqrt(np.mean(np.square(low))) or 0.0)
    ratio = low_rms / full_rms
    if ratio >= 0.46:
        return "heavy"
    if ratio >= 0.32:
        return "solid"
    return "medium"


def _drum_feel(kick_pattern: list[int]) -> str:
    if not kick_pattern:
        return "unknown"
    four = {0, 4, 8, 12, 16, 20, 24, 28}
    extras = [pos for pos in kick_pattern if pos not in four]
    missing_downbeats = [pos for pos in four if pos in range(0, 32) and pos not in kick_pattern]
    if len(extras) >= 4:
        return "funky syncopated kick with breaks"
    if extras:
        return "four-on-floor with mean offbeat kick accents"
    if missing_downbeats:
        return "broken club kick pattern"
    return "straight four-on-floor foundation"


def _bass_feel(bass_pattern: list[int]) -> str:
    if not bass_pattern:
        return "unknown"
    offbeats = [pos for pos in bass_pattern if pos % 4 not in (0,)]
    if len(offbeats) >= len(bass_pattern) * 0.55:
        return "syncopated bassline answering the kick"
    if len(bass_pattern) >= 10:
        return "busy rolling bassline"
    return "sparse heavy bass stabs"


def _club_energy(y, low, kick_pattern: list[int], bass_pattern: list[int]) -> str:
    import numpy as np

    rms = float(np.sqrt(np.mean(np.square(y))) or 0.0)
    low_rms = float(np.sqrt(np.mean(np.square(low))) or 0.0)
    hit_density = len(kick_pattern) + len(bass_pattern)
    if rms > 0.11 and low_rms > 0.04 and hit_density >= 12:
        return "banger"
    if rms > 0.08 and hit_density >= 8:
        return "club"
    return "restrained"


def _bass_notes(librosa, np, bass_band, sr: int, bpm: float) -> list[str]:
    hop = 512
    try:
        f0, voiced, _ = librosa.pyin(
            bass_band,
            fmin=librosa.note_to_hz("E1"),
            fmax=librosa.note_to_hz("C4"),
            sr=sr,
            hop_length=hop,
        )
    except Exception:
        return []
    if f0 is None:
        return []
    notes: list[str] = []
    counts: dict[str, int] = {}
    for freq, is_voiced in zip(f0, voiced):
        if not is_voiced or np.isnan(freq):
            continue
        midi = int(round(69 + 12 * math.log2(float(freq) / 440.0)))
        if not 28 <= midi <= 60:
            continue
        note = _NOTE_NAMES[midi % 12]
        counts[note] = counts.get(note, 0) + 1
    for note, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]:
        notes.append(note)
    return notes


def _bass_motif_16th(librosa, np, bass_band, sr: int, bpm: float, sixteenth: float, bass_pattern: list[int]) -> list[str]:
    hop = 512
    try:
        f0, voiced, _ = librosa.pyin(
            bass_band,
            fmin=librosa.note_to_hz("E1"),
            fmax=librosa.note_to_hz("C4"),
            sr=sr,
            hop_length=hop,
        )
    except Exception:
        return []
    if f0 is None:
        return []

    wanted_steps = set(bass_pattern or range(32))
    counts: dict[int, dict[str, int]] = {}
    for index, (freq, is_voiced) in enumerate(zip(f0, voiced)):
        if not is_voiced or np.isnan(freq):
            continue
        midi = int(round(69 + 12 * math.log2(float(freq) / 440.0)))
        if not 28 <= midi <= 60:
            continue
        time_seconds = index * hop / float(sr)
        step = int(round(time_seconds / sixteenth)) % 32
        if step not in wanted_steps:
            continue
        note = _NOTE_NAMES[midi % 12]
        counts.setdefault(step, {})
        counts[step][note] = counts[step].get(note, 0) + 1

    motif = []
    for step in sorted(counts):
        note_counts = counts[step]
        note = max(note_counts, key=note_counts.get)
        motif.append(f"{step}:{note}")
    return motif[:16]


def score_groove_similarity(reference_groove: dict | None, candidate_audio: str, bpm: float | None) -> dict:
    if not reference_groove:
        return {"score": 0.0, "warnings": ["Reference groove is unavailable."]}
    if reference_groove.get("method") in (None, "", "unavailable"):
        return {"score": 0.0, "warnings": reference_groove.get("warnings") or ["Reference groove is unavailable."]}
    candidate = analyze_reference_groove(candidate_audio, bpm)
    if candidate.get("method") in (None, "", "unavailable"):
        return {
            "score": 0.0,
            "warnings": candidate.get("warnings") or ["Candidate groove is unavailable."],
            "candidate_groove": candidate,
        }
    kick = _jaccard(reference_groove.get("kick_pattern_16th"), candidate.get("kick_pattern_16th"))
    bass = _jaccard(reference_groove.get("bass_accent_pattern_16th"), candidate.get("bass_accent_pattern_16th"))
    hats = _jaccard(reference_groove.get("hat_pattern_16th"), candidate.get("hat_pattern_16th"))
    notes = _jaccard(reference_groove.get("bass_notes"), candidate.get("bass_notes"))
    low = 1.0 if reference_groove.get("low_end_weight") == candidate.get("low_end_weight") else 0.45
    energy = 1.0 if reference_groove.get("club_energy") == candidate.get("club_energy") else 0.45
    score = 0.28 * kick + 0.28 * bass + 0.12 * hats + 0.14 * notes + 0.09 * low + 0.09 * energy
    return {
        "score": round(max(0.0, min(1.0, score)), 3),
        "kick_match": round(kick, 3),
        "bass_match": round(bass, 3),
        "hat_match": round(hats, 3),
        "bass_note_match": round(notes, 3),
        "candidate_groove": candidate,
    }


def _jaccard(left, right) -> float:
    left_set = {str(item) for item in (left or [])}
    right_set = {str(item) for item in (right or [])}
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / float(len(left_set | right_set))


def _build_prompt(
    kick_pattern: list[int],
    bass_pattern: list[int],
    hat_pattern: list[int],
    bass_motif: list[str],
    bass_notes: list[str],
    swing: float,
    low_end_weight: str,
    drum_feel: str,
    bass_feel: str,
    club_energy: str,
) -> str:
    parts = [
        f"reference groove fingerprint: {club_energy} underground club energy",
        f"{low_end_weight} low-end weight",
        drum_feel,
        bass_feel,
    ]
    if kick_pattern:
        parts.append(f"kick accents over two bars on 16th-grid positions {kick_pattern}")
    if bass_pattern:
        parts.append(f"bass accents over two bars on 16th-grid positions {bass_pattern}")
    if bass_motif:
        parts.append(f"bassline motif map step:note over two bars {bass_motif}")
    if hat_pattern:
        parts.append(f"hat/percussion accents over two bars on 16th-grid positions {hat_pattern}")
    if bass_notes:
        parts.append(f"bass tonal center uses notes {', '.join(bass_notes[:4])}")
    if swing >= 0.04:
        parts.append(f"noticeable swung hats around {round(swing, 2)} of a 16th late")
    parts.append("make it harder, darker, meaner, and less polite than generic deep house")
    return "; ".join(parts)


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run isolated reference groove analysis.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("audio_path")
    parser.add_argument("--bpm", type=float, default=124.0)
    parser.add_argument("--section-start", type=float, default=None)
    args = parser.parse_args()

    section = None
    if args.section_start is not None:
        section = {"start_seconds": args.section_start}
    payload = _analyze_reference_groove_unsafe(args.audio_path, args.bpm, section)
    if args.json:
        sys.stdout.write(json.dumps(payload, sort_keys=True))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(str(payload))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
