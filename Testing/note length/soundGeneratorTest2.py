import time
import wave
import numpy as np

SAMPLE_RATE = 44_100
BPM = 300
OUTPUT_FILE = "generated_music_offset.wav"
OFFSET_SECONDS = 0.015  # 15 ms steganographic offset
EXAMPLE_OFFSET = "1001001010" + "1001100101" + "1110010001" + "1001001010" + "1001100101" + "1110010001" + "1001001010" + "1001100101" + "1110010001"
PAUSE_SECONDS = 0.0

NOTE_FREQUENCIES = {
    "G3": 196.0000 * 2,
    "A3": 220.0000 * 2,
    "B3": 246.9417 * 2,
    "C4": 261.6256 * 2,
    "D4": 293.6648 * 2,
    "E4": 329.6276 * 2,
    "F4": 349.2282 * 2,
    "G4": 391.9954 * 2,
    "A4": 440.0000 * 2,
    "B4": 493.8833 * 2,
    "C5": 523.2511 * 2,
    "D5": 587.3295 * 2,
    "E5": 659.2551 * 2,
}


def envelope(
    t: np.ndarray | float,
    duration: float,
    attack: float = 0.005,
    release: float = 0.005,
) -> np.ndarray | float:
    """Apply short attack and release ramps to avoid clicks using vectorized NumPy operations."""
    t_arr = np.asarray(t, dtype=np.float64)
    env = np.ones_like(t_arr)

    # Attack ramp
    if attack > 0:
        att_mask = t_arr < attack
        env[att_mask] = t_arr[att_mask] / attack
    else:
        att_mask = np.zeros_like(t_arr, dtype=bool)

    # Release ramp
    if release > 0:
        rel_mask = (t_arr > (duration - release)) & (~att_mask)
        env[rel_mask] = np.maximum(0.0, (duration - t_arr[rel_mask]) / release)

    if np.isscalar(t):
        return float(env.item())
    return env


def make_tone(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Generate a single sine tone with attack/release envelope using NumPy."""
    sample_count = max(1, round(duration * sample_rate))
    t = np.arange(sample_count, dtype=np.float64) / sample_rate
    env = envelope(t, duration)
    return 0.35 * env * np.sin(2.0 * np.pi * frequency * t)


def apply_timing_offsets(
    notes: list[tuple[str | None, float]],
    offsets: float | list[float] | str | None = None,
    bpm: float = BPM,
) -> tuple[list[tuple[str | None, float]], np.ndarray]:
    """Apply note end timing offsets relative to the BPM grid for steganography.

    Modulates note durations so that each note's ending time is shifted to
    (nominal_grid_time + offset), allowing digital data to be embedded as rhythmic deviations.

    Parameters
    ----------
    notes : list of (pitch, beats)
        Original sequence of notes on the theoretical BPM grid.
    offsets : float, list[float], str, or None
        - If float: applies alternating +/- offset in seconds (e.g., 0.015 for +/-15 ms).
        - If list/array: explicit end offset (in seconds) for each note.
        - If str: binary string (e.g. '01101') or ASCII text encoded into +/- offsets.
    bpm : float
        Tempo in beats per minute.

    Returns
    -------
    adjusted_notes : list of (pitch, adjusted_beats)
        Notes with duration adjustments ready to be written to WAV.
    expected_offsets : np.ndarray
        Array of expected offsets (in seconds) for each note.
    """
    beat_s = 60.0 / bpm
    n = len(notes)

    if offsets is None or offsets == 0:
        offset_arr = np.zeros(n, dtype=np.float64)
    elif isinstance(offsets, (int, float)):
        # Alternating +offset, -offset for steganographic modulation
        offset_arr = np.array([offsets if i % 2 == 0 else -offsets for i in range(n)], dtype=np.float64)
    elif isinstance(offsets, str):
        # Convert text to binary string if not already bits
        if not all(c in "01" for c in offsets):
            bit_str = "".join(f"{ord(c):08b}" for c in offsets)
        else:
            bit_str = offsets
        step = 0.015  # Default 15ms step for binary data
        offset_arr = np.zeros(n, dtype=np.float64)
        for i in range(min(n, len(bit_str))):
            offset_arr[i] = step if bit_str[i] == "1" else -step
    else:
        arr = np.asarray(offsets, dtype=np.float64)
        offset_arr = np.pad(arr, (0, max(0, n - len(arr))))[:n]

    cum_time = 0.0
    prev_end = 0.0
    adjusted_notes: list[tuple[str | None, float]] = []

    for (pitch, beats), off in zip(notes, offset_arr):
        cum_time += beats * beat_s
        target_end = cum_time + off
        # Ensure positive duration (at least 10 ms)
        dur = max(0.01, target_end - prev_end)
        adjusted_notes.append((pitch, dur / beat_s))
        prev_end = prev_end + dur

    return adjusted_notes, offset_arr


def generate_audio(
    notes: list[tuple[str | None, float]],
    bpm: float = BPM,
    pause_seconds: float = PAUSE_SECONDS,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Generate normalized floating-point audio samples for the given list of notes.

    Tracks exact cumulative sample grid positions to eliminate timing and rounding drift.
    """
    seconds_per_beat = 60.0 / bpm
    total_beats = sum(b for _, b in notes)
    total_samples = int(round(total_beats * seconds_per_beat * sample_rate))
    output_buffer = np.zeros(total_samples, dtype=np.float64)

    tone_cache: dict[tuple[float, int], np.ndarray] = {}
    cum_beats = 0.0
    current_sample = 0

    for note, beats in notes:
        cum_beats += beats
        target_end_sample = int(round(cum_beats * seconds_per_beat * sample_rate))
        note_total_samples = target_end_sample - current_sample

        if note is not None:
            pause_samples = min(int(round(pause_seconds * sample_rate)), max(0, note_total_samples - 1))
            tone_samples = note_total_samples - pause_samples
            freq = NOTE_FREQUENCIES[note]

            cache_key = (freq, tone_samples)
            if cache_key not in tone_cache:
                t = np.arange(tone_samples, dtype=np.float64) / sample_rate
                duration = tone_samples / sample_rate
                env = envelope(t, duration)
                tone_cache[cache_key] = 0.35 * env * np.sin(2.0 * np.pi * freq * t)

            write_len = min(tone_samples, total_samples - current_sample)
            output_buffer[current_sample : current_sample + write_len] = tone_cache[cache_key][:write_len]

        current_sample = target_end_sample

    return output_buffer


def write_wav(
    filename: str,
    notes: list[tuple[str | None, float]],
    bpm: float = BPM,
    pause_seconds: float = PAUSE_SECONDS,
    sample_rate: int = SAMPLE_RATE,
) -> None:
    """Generate audio and write to a 16-bit PCM WAV file using NumPy vectorization."""
    samples = generate_audio(
        notes,
        bpm=bpm,
        pause_seconds=pause_seconds,
        sample_rate=sample_rate,
    )

    # Fast vectorized conversion to 16-bit little-endian PCM
    pcm_data = np.clip(np.round(samples * 32767.0), -32768, 32767).astype("<i2")

    with wave.open(filename, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm_data.tobytes())


MELODY_LOOP: list[tuple[str | None, float]] = [
    # --- PARTE 1: Introdução Suave (16 tempos) ---
    ("A3", 2), ("C4", 1), ("D4", 1),
    ("E4", 2), ("D4", 1), ("C4", 1),
    ("D4", 2), ("E4", 1), ("C4", 1),
    ("A3", 3), (None, 1),

    # --- PARTE 2: Variação Ascendente (16 tempos) ---
    ("A3", 2), ("C4", 1), ("D4", 1),
    ("E4", 2), ("G4", 1), ("A4", 1),
    ("G4", 2), ("E4", 1), ("D4", 1),
    ("E4", 3), (None, 1),

    # --- PARTE 3: Clímax (16 tempos) ---
    ("A4", 2), ("G4", 1), ("E4", 1),
    ("D4", 2), ("E4", 1), ("G4", 1),
    ("A4", 2), ("G4", 1), ("E4", 1),
    ("D4", 3), (None, 1),

    # --- PARTE 4: A Ponte de Retorno / Sem Pausas (16 tempos) ---
    ("E4", 2), ("D4", 1), ("C4", 1),
    ("A3", 2), ("G3", 1), ("A3", 1),
    ("C4", 2), ("D4", 2),
    # A mágica do loop perfeito acontece nesta linha abaixo:
    # Estas 4 notas rápidas emendam exatamente no "A3" lá do início.
    ("E4", 1), ("D4", 1), ("C4", 1), ("G3", 1),
] * 2

# Alias for backwards compatibility with original naming
melodyLoop = MELODY_LOOP


if __name__ == "__main__":
    # Base melody
    notes = MELODY_LOOP.copy()

    # --- STEGANOGRAPHY / TIMING OFFSET SECTION ---
    # Applied at the end of the program, right before write_wav.
    # Set OFFSET_SECONDS (e.g. 0.015 for +/-15 ms, 0.020 for +/-20 ms, or 0.0 for pure BPM grid)
    # Or specify custom bitstring or offsets array: e.g. offsets="01010101"
    stego_notes, expected_offsets = apply_timing_offsets(notes, offsets=EXAMPLE_OFFSET, bpm=BPM)

    start_time = time.perf_counter()
    write_wav(OUTPUT_FILE, stego_notes, bpm=BPM)
    elapsed_time = (time.perf_counter() - start_time) * 1000

    print(f"Generated {OUTPUT_FILE} at {BPM} BPM in {elapsed_time:.2f} ms")
    if np.any(expected_offsets != 0):
        print(f"Applied steganographic offset: +/-{OFFSET_SECONDS * 1000:.1f} ms across {len(stego_notes)} notes")
