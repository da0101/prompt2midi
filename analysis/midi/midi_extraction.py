#!/usr/bin/env python3
"""Small MIDI sketch writer used by the local analysis pipeline."""

from __future__ import annotations

import argparse
import os
import struct


NOTE_TO_MIDI = {
    "C": 48,
    "C#": 49,
    "D": 50,
    "D#": 51,
    "E": 52,
    "F": 53,
    "F#": 54,
    "G": 55,
    "G#": 56,
    "A": 57,
    "A#": 58,
    "B": 59,
}


def write_note_events_midi(path: str, events: list[dict], bpm: float = 120.0) -> str:
    ticks_per_beat = 480
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    data = _build_track_data(events, bpm, ticks_per_beat, include_meta=True)
    _write_single_track(path, data, ticks_per_beat)
    return os.path.abspath(path)


def write_multitrack_midi(path: str, tracks: list[list[dict]], bpm: float = 120.0) -> str:
    """Write a format-1 multi-track MIDI file; each element of tracks is an events list."""
    ticks_per_beat = 480
    tempo = int(60_000_000 / max(40.0, min(220.0, bpm or 120.0)))

    meta = bytearray()
    meta.extend(_varlen(0) + b"\xff\x51\x03" + tempo.to_bytes(3, "big"))
    meta.extend(_varlen(0) + b"\xff\x2f\x00")

    chunks = [b"MTrk" + struct.pack(">I", len(meta)) + bytes(meta)]
    for events in tracks:
        data = _build_track_data(events, bpm, ticks_per_beat, include_meta=False)
        chunks.append(b"MTrk" + struct.pack(">I", len(data)) + bytes(data))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), ticks_per_beat)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        for chunk in chunks:
            f.write(chunk)
    return os.path.abspath(path)


def _build_track_data(
    events: list[dict], bpm: float, ticks_per_beat: int, include_meta: bool = True
) -> bytes:
    tempo = int(60_000_000 / max(40.0, min(220.0, bpm or 120.0)))
    sorted_events = sorted(events, key=lambda e: float(e.get("start", 0.0)))
    track_events: list[tuple[int, bytes]] = []
    if include_meta:
        track_events.append((0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")))
    for event in sorted_events:
        start_tick = _seconds_to_ticks(float(event.get("start", 0.0)), bpm, ticks_per_beat)
        duration = max(0.05, float(event.get("duration", 0.25)))
        end_tick = start_tick + _seconds_to_ticks(duration, bpm, ticks_per_beat)
        pitch = max(0, min(127, int(event.get("midi_note", 48))))
        velocity = max(1, min(127, int(event.get("velocity", 86))))
        channel = max(0, min(15, int(event.get("channel", 0))))
        track_events.append((start_tick, bytes([0x90 | channel, pitch, velocity])))
        track_events.append((end_tick,   bytes([0x80 | channel, pitch, 0])))
    data = bytearray()
    cursor = 0
    for tick, message in sorted(track_events, key=lambda item: (item[0], (item[1][0] & 0xF0) == 0x90)):
        data.extend(_varlen(max(0, tick - cursor)) + message)
        cursor = tick
    data.extend(_varlen(0) + b"\xff\x2f\x00")
    return bytes(data)


def write_reference_sketch_midi(path: str, key: str = "C major", bpm: float = 120.0, bars: int = 4) -> str:
    """Write a generated reference sketch, not a transcription of the source."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    root = key.split()[0] if key else "C"
    note = NOTE_TO_MIDI.get(root, 48)
    ticks_per_beat = 480
    beat_ticks = ticks_per_beat
    tempo = int(60_000_000 / max(40.0, min(220.0, bpm or 120.0)))

    events = bytearray()
    events.extend(_varlen(0) + b"\xff\x51\x03" + tempo.to_bytes(3, "big"))
    events.extend(_varlen(0) + b"\xc0\x20")

    pattern = [note, note + 7, note + 10, note + 7]
    for _bar in range(bars):
        for pitch in pattern:
            events.extend(_varlen(0) + bytes([0x90, pitch, 92]))
            events.extend(_varlen(beat_ticks) + bytes([0x80, pitch, 0]))

    events.extend(_varlen(0) + b"\xff\x2f\x00")

    _write_single_track(path, events, ticks_per_beat)
    return os.path.abspath(path)


def _seconds_to_ticks(seconds: float, bpm: float, ticks_per_beat: int) -> int:
    beats = seconds / (60.0 / max(40.0, min(220.0, bpm or 120.0)))
    return max(0, round(beats * ticks_per_beat))


def _write_single_track(path: str, events: bytes | bytearray, ticks_per_beat: int) -> None:
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks_per_beat)
    track = b"MTrk" + struct.pack(">I", len(events)) + bytes(events)
    with open(path, "wb") as midi_file:
        midi_file.write(header + track)


def _varlen(value: int) -> bytes:
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
        value >>= 7

    output = bytearray()
    while True:
        output.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a simple reference-sketch MIDI file.")
    parser.add_argument("output_path")
    parser.add_argument("--key", default="C major")
    parser.add_argument("--bpm", type=float, default=120.0)
    args = parser.parse_args()
    print(write_reference_sketch_midi(args.output_path, key=args.key, bpm=args.bpm))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
