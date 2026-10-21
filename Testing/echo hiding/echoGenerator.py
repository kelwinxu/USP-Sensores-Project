#!/usr/bin/env python3
"""Echo Hiding Steganography Sound Generator.

Synthesizes the looping music (MELODY_LOOP) and embeds hidden data using
the Single-Kernel Echo Hiding steganography technique.

Reference Implementation:
    Kadir Tekeli, "Audio Steganography Algorithms"
    https://github.com/ktekeli/audio-steganography-algorithms
    (02-Echo-Hiding/01-Echo-Hiding-Single-Kernel)
"""

import argparse
import math
import os
import sys
import time
import wave
import numpy as np

# --- Default Parameters ---
SAMPLE_RATE = 44100
BPM = 300
DEFAULT_D0 = 150          # Delay rate for bit 0 (samples, ~3.40 ms at 44.1 kHz)
DEFAULT_D1 = 200          # Delay rate for bit 1 (samples, ~4.54 ms at 44.1 kHz)
DEFAULT_ALPHA = 0.5       # Echo amplitude attenuation factor
DEFAULT_FRAME_LEN = 8192  # Length of frames L (matching Tekeli: 8*1024)
DEFAULT_K = 256           # Mixer transition smoothing length (samples)
DEFAULT_OUTPUT = "echo_stego_music.wav"
DEFAULT_MESSAGE = "Texto de teste a ser gravado em áudio, teste para ver o quão longo o texto pode ser inserido sem perder informação"

NOTE_FREQUENCIES: dict[str, float] = {
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

# The canonical looping melody (4 parts, 16 beats each = 64 beats per cycle)
MELODY_PHRASE: list[tuple[str | None, float]] = [
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
    ("E4", 1), ("D4", 1), ("C4", 1), ("G3", 1),
]

# Standard 2-loop melody matching soundGeneratorTest2.py
MELODY_LOOP: list[tuple[str | None, float]] = MELODY_PHRASE * 2


def envelope(
    t: np.ndarray,
    duration: float,
    attack: float = 0.005,
    release: float = 0.005,
) -> np.ndarray:
    """Apply short attack and release ramps to avoid clicks using vectorized NumPy operations."""
    env = np.ones_like(t, dtype=np.float64)
    if attack > 0:
        att_mask = t < attack
        env[att_mask] = t[att_mask] / attack
    else:
        att_mask = np.zeros_like(t, dtype=bool)

    if release > 0:
        rel_mask = (t > (duration - release)) & (~att_mask)
        env[rel_mask] = np.maximum(0.0, (duration - t[rel_mask]) / release)
    return env


def synthesize_melody(
    notes: list[tuple[str | None, float]],
    bpm: float = BPM,
    sample_rate: int = SAMPLE_RATE,
    pause_seconds: float = 0.0,
    dither_amp: float = 0.004,
) -> np.ndarray:
    """Synthesize floating-point audio samples for the note sequence with sample-accurate timing.

    Parameters
    ----------
    notes : list of (pitch, beats)
        Note sequence to render.
    bpm : float
        Tempo in beats per minute.
    sample_rate : int
        Audio sampling rate in Hz.
    pause_seconds : float
        Optional silence pause before note attack.
    dither_amp : float
        Subtle analog dithering amplitude (~ -38 dB). Echo hiding requires broadband spectral
        content across the FFT bins to form cepstral ripples; this subtle warmth guarantees
        flawless echo detection even during musical rests and pure tones without audible degradation.

    Returns
    -------
    np.ndarray
        Floating-point audio signal.
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

    # Add subtle analog dithering floor to provide broadband spectral excitation for cepstrum analysis
    if dither_amp > 0:
        rng = np.random.default_rng(seed=42)
        dither = rng.normal(0.0, dither_amp, size=total_samples)
        output_buffer += dither

    return output_buffer


def text_to_bits(text: str) -> str:
    """Convert an ASCII string to a binary bit sequence (8 bits per character, MSB first).

    Equivalent to getBits.m in the reference repository.
    """
    return "".join(f"{ord(c):08b}" for c in text)


def mixer(
    L: int,
    bits: str,
    lower: float = 0.0,
    upper: float = 1.0,
    K: int = DEFAULT_K,
) -> np.ndarray:
    """Generate a smoothed mixer transition signal between consecutive bit frames.

    Direct Python implementation of mixer.m from Kadir Tekeli's reference repository.
    Applies Hann window convolution to eliminate audible clicks and discontinuities at bit boundaries.

    Parameters
    ----------
    L : int
        Frame length in samples.
    bits : str
        Binary sequence of '0' and '1'.
    lower : float
        Lower amplitude bound of the mixer signal.
    upper : float
        Upper amplitude bound of the mixer signal.
    K : int
        Length of the smoothing window in samples.

    Returns
    -------
    np.ndarray
        Smoothed mixer signal of length len(bits) * L.
    """
    if 2 * K > L:
        K = (L // 4) - ((L // 4) % 4)
    else:
        K = K - (K % 4)
    K = max(4, K)

    N = len(bits)
    encbit = np.array([int(b) for b in bits], dtype=np.float64)
    m_sig = np.repeat(encbit, L)

    # Hann window calculation
    n = np.arange(K, dtype=np.float64)
    hann = 0.5 * (1.0 - np.cos(2.0 * np.pi * n / (K - 1)))
    c = np.convolve(m_sig, hann, mode="full")

    start = K // 2
    wnorm = c[start : start + N * L].copy()
    max_c = np.max(np.abs(c))
    if max_c > 0:
        wnorm /= max_c

    w_sig = wnorm * (upper - lower) + lower
    return w_sig

def echo_enc(
    signal: np.ndarray,
    message: str,
    d0: int = DEFAULT_D0,
    d1: int = DEFAULT_D1,
    alpha: float = DEFAULT_ALPHA,
    L: int = DEFAULT_FRAME_LEN,
    K: int = DEFAULT_K,
) -> tuple[np.ndarray, str]:
    """Single-Kernel Echo Hiding Encoder.

    Direct Python implementation of echo_enc_single.m from Kadir Tekeli's reference repository.

    Parameters
    ----------
    signal : np.ndarray
        Cover audio signal (1D float array).
    message : str
        ASCII text message or bitstring ('0' and '1') to embed.
    d0 : int
        Delay rate in samples for bit 0.
    d1 : int
        Delay rate in samples for bit 1.
    alpha : float
        Echo amplitude attenuation factor (0.0 < alpha < 1.0).
    L : int
        Frame length in samples.
    K : int
        Smoothing mixer window length in samples.

    Returns
    -------
    stego_signal : np.ndarray
        Signal with embedded echo steganography.
    embedded_bits : str
        The final bit sequence embedded into the audio (including padding/truncation).
    """
    # Convert message to binary if not already a bit string
    if not all(c in "01" for c in message):
        raw_bits = text_to_bits(message)
    else:
        raw_bits = message

    total_len = len(signal)
    nframe = total_len // L
    N = nframe - (nframe % 8)  # Round down to multiple of 8 for complete bytes

    if len(raw_bits) > N:
        print(f"[WARN] Message exceeds capacity ({len(raw_bits)} bits > {N} bits). Truncating message!")
        bits = raw_bits[:N]
    else:
        # Zero-pad trailing bits up to frame capacity N (matching reference)
        bits = raw_bits + "0" * (N - len(raw_bits))

    # Single-echo kernels for bit 0 and bit 1:
    # Filter with [zeros(d, 1); 1]*alpha is equivalent to delaying by d samples and multiplying by alpha
    echo_zro = np.zeros_like(signal)
    if d0 < len(signal):
        echo_zro[d0:] = alpha * signal[:-d0]

    echo_one = np.zeros_like(signal)
    if d1 < len(signal):
        echo_one[d1:] = alpha * signal[:-d1]

    # Generate smooth mixer signal
    mix = mixer(L, bits, lower=0.0, upper=1.0, K=K)

    # Embed message into frames
    stego = signal.copy()
    embedded_region_len = N * L
    stego[:embedded_region_len] = (
        signal[:embedded_region_len]
        + echo_zro[:embedded_region_len] * (1.0 - mix)
        + echo_one[:embedded_region_len] * mix
    )

    return stego, bits


def write_wav(
    filename: str,
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
) -> None:
    """Save floating-point audio samples to a 16-bit PCM mono WAV file."""
    pcm_data = np.clip(np.round(samples * 32767.0), -32768, 32767).astype("<i2")
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    with wave.open(filename, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm_data.tobytes())


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Echo Hiding Steganography Sound Generator (Reference: Kadir Tekeli)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-m", "--message",
        type=str,
        default=DEFAULT_MESSAGE,
        help="Text message or binary bitstring to embed into the audio",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=DEFAULT_OUTPUT,
        help="Output WAV file path",
    )
    parser.add_argument(
        "--bpm",
        type=float,
        default=BPM,
        help="Tempo in BPM",
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=None,
        help="Number of melody loop repetitions (auto-calculated if message needs more space)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help="Echo attenuation factor alpha",
    )
    parser.add_argument(
        "--d0",
        type=int,
        default=DEFAULT_D0,
        help="Delay in samples for bit 0",
    )
    parser.add_argument(
        "--d1",
        type=int,
        default=DEFAULT_D1,
        help="Delay in samples for bit 1",
    )
    parser.add_argument(
        "-L", "--frame-len",
        type=int,
        default=DEFAULT_FRAME_LEN,
        help="Frame length L in samples",
    )
    parser.add_argument(
        "--clean-wav",
        type=str,
        default=None,
        help="Optional path to also save the clean un-embedded cover WAV file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    # Determine required loop count based on message length and frame length
    message = args.message
    is_bitstring = all(c in "01" for c in message)
    required_bits = len(message) if is_bitstring else len(message) * 8

    samples_per_cycle = int(round(64 * (60.0 / args.bpm) * SAMPLE_RATE))
    frames_per_cycle = samples_per_cycle // args.frame_len

    if args.loops is not None:
        num_loops = max(1, args.loops)
    else:
        # Default is at least 2 loops, or more if needed to fit the message
        needed_cycles = max(2, math.ceil(required_bits / max(1, frames_per_cycle)))
        num_loops = needed_cycles

    notes = MELODY_PHRASE * num_loops

    print("=" * 65)
    print(" ECHO HIDING SOUND GENERATOR ")
    print(" Reference: Kadir Tekeli (audio-steganography-algorithms) ")
    print("=" * 65)
    print(f"BPM: {args.bpm} | Sample Rate: {SAMPLE_RATE} Hz | Melody Cycles: {num_loops}")
    print(f"Echo parameters: d0 = {args.d0} samples, d1 = {args.d1} samples, alpha = {args.alpha}")
    print(f"Frame length L: {args.frame_len} samples ({args.frame_len / SAMPLE_RATE * 1000:.1f} ms)")

    # 1. Synthesize cover music
    t_start = time.perf_counter()
    cover_audio = synthesize_melody(notes, bpm=args.bpm, sample_rate=SAMPLE_RATE)
    duration_s = len(cover_audio) / SAMPLE_RATE

    max_frames = (len(cover_audio) // args.frame_len)
    max_frames = max_frames - (max_frames % 8)
    max_bytes = max_frames // 8

    print(f"Audio Duration: {duration_s:.2f} s ({len(cover_audio):,} samples)")
    print(f"Steganography Capacity: {max_frames} bits ({max_bytes} bytes/characters)")
    print(f"Message to Embed: {repr(message)}")
    print(f"Message Length: {len(message)} {'bits' if is_bitstring else 'characters'} ({required_bits} bits)")

    # 2. Embed message using Echo Hiding
    stego_audio, embedded_bits = echo_enc(
        cover_audio,
        message=message,
        d0=args.d0,
        d1=args.d1,
        alpha=args.alpha,
        L=args.frame_len,
        K=DEFAULT_K,
    )

    # 3. Save WAV files
    write_wav(args.output, stego_audio, sample_rate=SAMPLE_RATE)
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    print(f"\n[SUCCESS] Wrote Stego Audio: {os.path.abspath(args.output)}")
    print(f"Embedded bit sequence (first 32 bits): {embedded_bits[:32]}...")
    print(f"Total processing time: {elapsed_ms:.2f} ms")

    if args.clean_wav:
        write_wav(args.clean_wav, cover_audio, sample_rate=SAMPLE_RATE)
        print(f"[SUCCESS] Wrote Clean Audio: {os.path.abspath(args.clean_wav)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
