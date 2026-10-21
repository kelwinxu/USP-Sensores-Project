#!/usr/bin/env python3
"""Echo Hiding Steganography Sound Reader / Decoder.

Extracts hidden digital data (text or binary bitstrings) from an audio WAV file
using Real Cepstrum analysis of single-kernel echo delays.

Reference Implementation:
    Kadir Tekeli, "Audio Steganography Algorithms"
    https://github.com/ktekeli/audio-steganography-algorithms
    (02-Echo-Hiding/01-Echo-Hiding-Single-Kernel)
"""

import argparse
import os
import sys
import time
import wave
import numpy as np

# --- Default Parameters matching Kadir Tekeli reference ---
DEFAULT_D0 = 150          # Delay rate for bit 0 (samples)
DEFAULT_D1 = 200          # Delay rate for bit 1 (samples)
DEFAULT_FRAME_LEN = 8192  # Length of frame L (matching Tekeli: 8*1024)
DEFAULT_INPUT = "microfone3.wav"

#1 Longo
#2 Curto
#3 Curto distante
#4 Curto distante + ruido


def load_wav(filename: str) -> tuple[np.ndarray, int]:
    """Load a WAV audio file and return normalized floating-point mono audio and sample rate.

    Supports 8-bit unsigned PCM, 16-bit signed PCM, 24-bit PCM, 32-bit signed PCM,
    and 32-bit IEEE float formats.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Audio file not found: {filename}")

    with wave.open(filename, "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        n_frames = wav.getnframes()
        raw_bytes = wav.readframes(n_frames)

    if width == 1:
        # 8-bit unsigned PCM (0 to 255, centered at 128)
        audio = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        # 16-bit signed PCM little-endian
        audio = np.frombuffer(raw_bytes, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        # 24-bit signed PCM little-endian
        raw_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        reshaped = raw_arr.reshape(-1, 3)
        # Pad 3 bytes to 4 bytes signed int32
        padded = np.column_stack((np.zeros((len(reshaped), 1), dtype=np.uint8), reshaped))
        audio = padded.view("<i4").astype(np.float64) / 2147483648.0
    elif width == 4:
        # 32-bit signed PCM or float32
        try:
            audio = np.frombuffer(raw_bytes, dtype="<i4").astype(np.float64) / 2147483648.0
        except Exception:
            audio = np.frombuffer(raw_bytes, dtype=np.float32).astype(np.float64)
    else:
        raise ValueError(f"Unsupported sample width: {width * 8} bits")

    # Downmix multi-channel to mono
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    return audio, sample_rate


def echo_dec(
    signal: np.ndarray,
    L: int = DEFAULT_FRAME_LEN,
    d0: int = DEFAULT_D0,
    d1: int = DEFAULT_D1,
    len_msg: int | None = None,
) -> tuple[str, str, list[dict]]:
    """Single-Kernel Echo Hiding Decoder using Real Cepstrum.

    Direct Python implementation of echo_dec.m from Kadir Tekeli's reference repository.

    Parameters
    ----------
    signal : np.ndarray
        Received stego audio signal (1D float array).
    L : int
        Frame length in samples.
    d0 : int
        Echo delay rate for bit 0.
    d1 : int
        Echo delay rate for bit 1.
    len_msg : int or None
        Expected message length in characters. If specified, extracts the exact number of characters.

    Returns
    -------
    bit_sequence : str
        Decoded binary sequence of '0' and '1'.
    message_text : str
        Decoded ASCII message text.
    frame_stats : list of dict
        Frame-by-frame analysis including cepstral peak values and decision margin.
    """
    total_len = len(signal)
    N = total_len // L

    bits: list[str] = []
    frame_stats: list[dict] = []

    for k in range(N):
        frame = signal[k * L : (k + 1) * L]

        # Real Cepstrum: Re(IFFT(ln(|FFT(x)| + eps)))
        # Note: in Python 0-based indexing, lag d0 corresponds to index d0, matching MATLAB rceps(d0+1)
        spec = np.abs(np.fft.fft(frame))
        log_spec = np.log(spec + 1e-12)
        rceps = np.real(np.fft.ifft(log_spec))

        c0 = float(rceps[d0])
        c1 = float(rceps[d1])

        # Decision rule: if rceps(d0+1) >= rceps(d1+1) -> bit = 0, else 1
        bit = "0" if c0 >= c1 else "1"
        bits.append(bit)

        frame_stats.append({
            "frame_idx": k,
            "c0": c0,
            "c1": c1,
            "margin": abs(c0 - c1),
            "bit": bit,
            "rms": float(np.sqrt(np.mean(frame**2))),
        })

    bit_str = "".join(bits)

    # Convert binary sequence to 8-bit ASCII characters
    m = N // 8
    chars: list[str] = []
    for i in range(m):
        byte = bit_str[i * 8 : (i + 1) * 8]
        chars.append(chr(int(byte, 2)))
    full_text = "".join(chars)

    if len_msg is not None and len_msg > 0:
        retrieved_text = full_text[:len_msg]
    else:
        # Strip trailing null characters (\x00) resulting from zero-padding
        retrieved_text = full_text.rstrip("\x00")

    return bit_str, retrieved_text, frame_stats


def calculate_ber(expected_bits: str, retrieved_bits: str) -> float:
    """Calculate Bit Error Rate (BER) between expected and retrieved bit sequences.

    Matches BER.m in the reference repository:
        BER = sum(abs(expected - retrieved)) / length
    """
    n = min(len(expected_bits), len(retrieved_bits))
    if n == 0:
        return 0.0
    errors = sum(1 for b1, b2 in zip(expected_bits[:n], retrieved_bits[:n]) if b1 != b2)
    return errors / n


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Echo Hiding Steganography Sound Reader / Decoder (Reference: Kadir Tekeli)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input_wav",
        type=str,
        nargs="?",
        default=DEFAULT_INPUT,
        help="Input WAV file containing hidden echo steganography data",
    )
    parser.add_argument(
        "-n", "--len-msg",
        type=int,
        default=None,
        help="Known length of the hidden message in characters (optional)",
    )
    parser.add_argument(
        "--d0",
        type=int,
        default=DEFAULT_D0,
        help="Echo delay rate in samples for bit 0",
    )
    parser.add_argument(
        "--d1",
        type=int,
        default=DEFAULT_D1,
        help="Echo delay rate in samples for bit 1",
    )
    parser.add_argument(
        "-L", "--frame-len",
        type=int,
        default=DEFAULT_FRAME_LEN,
        help="Frame length L in samples",
    )
    parser.add_argument(
        "-e", "--expected-message",
        type=str,
        default=None,
        help="Expected text message for automatic Bit Error Rate (BER) calculation",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print frame-by-frame cepstral analysis and metrics",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    print("=" * 65)
    print(" ECHO HIDING SOUND READER / DECODER ")
    print(" Reference: Kadir Tekeli (audio-steganography-algorithms) ")
    print("=" * 65)
    print(f"Reading Audio File: {os.path.abspath(args.input_wav)}")

    # 1. Load audio
    t_start = time.perf_counter()
    try:
        audio, sample_rate = load_wav(args.input_wav)
    except Exception as exc:
        print(f"[ERROR] Failed to load audio: {exc}", file=sys.stderr)
        sys.exit(1)

    duration_s = len(audio) / sample_rate
    num_frames = len(audio) // args.frame_len
    num_bytes = num_frames // 8

    print(f"Sample Rate: {sample_rate} Hz | Duration: {duration_s:.2f} s ({len(audio):,} samples)")
    print(f"Frame length L: {args.frame_len} samples ({args.frame_len / sample_rate * 1000:.1f} ms)")
    print(f"Analysis Frames: {num_frames} frames ({num_bytes} full ASCII bytes)")
    print(f"Echo Delays: d0 = {args.d0} samples ({args.d0 / sample_rate * 1000:.2f} ms), "
          f"d1 = {args.d1} samples ({args.d1 / sample_rate * 1000:.2f} ms)")

    # 2. Extract hidden bits using Real Cepstrum
    bits, text, stats = echo_dec(
        audio,
        L=args.frame_len,
        d0=args.d0,
        d1=args.d1,
        len_msg=args.len_msg,
    )
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    # 3. Print frame-by-frame analysis if requested
    if args.verbose:
        print("\n--- Frame Analysis Breakdown ---")
        for s in stats:
            print(f"Frame {s['frame_idx']:03d}: ceps[d0]={s['c0']:+8.4f} | ceps[d1]={s['c1']:+8.4f} "
                  f"| margin={s['margin']:.4f} | Bit={s['bit']} | RMS={s['rms']:.4f}")

    # 4. Display Results
    avg_margin = float(np.mean([s["margin"] for s in stats])) if stats else 0.0

    print("\n" + "-" * 65)
    print(" EXTRACTION RESULTS ")
    print("-" * 65)
    print(f"Decoded Bits (first 64 bits): {bits[:64]}...")
    print(f"Total Bits Extracted:         {len(bits)}")
    print(f"Decoded Message (Clean):      {repr(text)}")
    print(f"Average Detection Margin:     {avg_margin:.6f}")
    print(f"Decoding Time:                {elapsed_ms:.2f} ms")

    # 5. BER verification if expected message provided
    if args.expected_message is not None:
        expected_msg = args.expected_message
        if all(c in "01" for c in expected_msg):
            expected_bits = expected_msg
        else:
            expected_bits = "".join(f"{ord(c):08b}" for c in expected_msg)

        ber = calculate_ber(expected_bits, bits)
        if all(c in "01" for c in expected_msg):
            exact_match = bits.startswith(expected_msg)
        else:
            exact_match = (text == expected_msg) or (text.startswith(expected_msg))
        match_status = "PERFECT (100% Match)" if (ber == 0.0 and exact_match) else "MISMATCH"

        print("-" * 65)
        print(" VERIFICATION ")
        print("-" * 65)
        print(f"Expected Message:             {repr(expected_msg)}")
        print(f"Bit Error Rate (BER):         {ber:.4f} ({ber * 100:.2f}%)")
        print(f"Status:                       {match_status}")

    print("=" * 65)


if __name__ == "__main__":
    main()
