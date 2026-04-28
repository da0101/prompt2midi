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

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks_per_beat)
    track = b"MTrk" + struct.pack(">I", len(events)) + bytes(events)
    with open(path, "wb") as midi_file:
        midi_file.write(header + track)
    return os.path.abspath(path)


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
