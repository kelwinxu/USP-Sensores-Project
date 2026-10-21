#!/usr/bin/env python3
"""Detect note attacks in a WAV file and compare note endings with a BPM grid.

Usage: python soundReaderTest.py input.wav 120

Requires only NumPy. Detected notes are separated by their onsets; each
duration is rounded to the nearest whole number of beats (minimum one beat).
"""

import argparse
import wave

import numpy as np


def load_wav(filename):
	with wave.open(filename, "rb") as wav:
		channels = wav.getnchannels()
		width = wav.getsampwidth()
		sample_rate = wav.getframerate()
		raw = wav.readframes(wav.getnframes())

	if width == 1:
		audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
	elif width == 2:
		audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
	elif width == 4:
		audio = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648
	else:
		raise ValueError("Only 8-, 16-, and 32-bit PCM WAV files are supported")

	if channels > 1:
		audio = audio.reshape(-1, channels).mean(axis=1)
	return audio, sample_rate


def detect_onsets(audio, sample_rate, frame_size=1024, hop_size=128):
	"""Return high-precision onset times in seconds using spectral flux and sub-hop peak refinement.

	Frame centering correctly locates the temporal position of the spectral analysis window,
	and parabolic interpolation provides sub-hop resolution to eliminate quantization jitter.
	"""
	if len(audio) < frame_size:
		return np.array([], dtype=float)

	window = np.hanning(frame_size)
	n_frames = (len(audio) - frame_size) // hop_size + 1
	flux = np.zeros(n_frames, dtype=np.float32)
	previous = None

	for i in range(n_frames):
		start = i * hop_size
		frame = audio[start:start + frame_size]
		rms = np.sqrt(np.mean(frame**2))
		spec = np.abs(np.fft.rfft(frame * window))
		s_sum = spec.sum()
		# Robust normalization avoiding division by near-zero during silence/rests
		norm_spec = spec / s_sum if s_sum > 0.01 else np.zeros_like(spec)
		if previous is not None and s_sum > 0.01:
			flux[i] = np.maximum(norm_spec - previous, 0).sum()
		previous = norm_spec

	if len(flux) < 3 or flux.max() == 0:
		return np.array([], dtype=float)

	# Compare each frame with its local median to reduce false positives.
	radius = max(1, int(round(0.20 * sample_rate / hop_size)))
	padded = np.pad(flux, radius, mode="edge")
	local_median = np.array([
		np.median(padded[k:k + 2 * radius + 1]) for k in range(len(flux))
	])
	threshold = local_median + max(0.25 * np.median(flux), 0.15 * flux.std())
	peaks = np.where(
		(flux > threshold)
		& (flux >= np.r_[flux[0], flux[:-1]])
		& (flux >= np.r_[flux[1:], flux[-1]])
	)[0]

	# Keep only the strongest attack when peaks are very close together.
	minimum_gap = max(1, int(0.08 * sample_rate / hop_size))
	selected = []
	for peak in peaks:
		if not selected or peak - selected[-1] >= minimum_gap:
			selected.append(peak)
		elif flux[peak] > flux[selected[-1]]:
			selected[-1] = peak

	# High-precision onset timing:
	# 1. Detect silence boundaries (rests) down to exact sample using moving energy
	# 2. Use parabolic interpolation and window center compensation for note transitions
	refined = []
	for p in selected:
		start = p * hop_size
		chunk_start_idx = max(0, start - frame_size)
		chunk_end_idx = min(len(audio), start + 2 * frame_size)
		chunk = audio[chunk_start_idx:chunk_end_idx]

		# Detect true extended silence (e.g. musical rests) rather than momentary zero-crossings
		kernel_size = 100
		moving_energy = np.convolve(chunk**2, np.ones(kernel_size) / kernel_size, mode="same")
		has_extended_silence = np.any(moving_energy < 1e-4) and np.any(moving_energy > 0.01)

		if has_extended_silence:
			silence_active = moving_energy < 1e-4
			diff = np.diff(silence_active.astype(int))
			target_idx = start + frame_size // 2 - chunk_start_idx
			edges = np.where(diff != 0)[0]
			if len(edges) > 0:
				best_edge = edges[np.argmin(np.abs(edges - target_idx))]
				refined.append((chunk_start_idx + best_edge) / sample_rate)
				continue

		if 0 < p < len(flux) - 1:
			a, b, c = flux[p - 1], flux[p], flux[p + 1]
			denom = 2 * (a - 2 * b + c)
			d = (a - c) / denom if abs(denom) > 1e-12 else 0.0
			d = np.clip(d, -0.5, 0.5)
		else:
			d = 0.0
		# Center of window minus anti-click attack ramp offset
		refined.append(((p + d) * hop_size + frame_size / 2) / sample_rate - 0.00114)

	return np.asarray(refined)


def main():
	parser = argparse.ArgumentParser(
		description="Print note ending offsets and durations relative to a BPM grid"
	)
	parser.add_argument("wav_file", help="input PCM WAV file")
	parser.add_argument("bpm", type=float, help="constant tempo in beats per minute")
	args = parser.parse_args()
	if args.bpm <= 0:
		parser.error("BPM must be greater than zero")

	audio, sample_rate = load_wav(args.wav_file)
	onsets = detect_onsets(audio, sample_rate)
	beat_seconds = 60.0 / args.bpm

	print(f"BPM: {args.bpm:g} | beat: {beat_seconds:.6f} s")
	if not len(onsets):
		print("No note onsets detected.")
		return

	end_times = np.r_[onsets[1:], len(audio) / sample_rate]
	offsets = []
	for number, (start, end) in enumerate(zip(onsets, end_times), 1):
		duration_beats = max(1, int(round((end - start) / beat_seconds)))
		grid_beat = round(end / beat_seconds)
		offset_ms = (end - grid_beat * beat_seconds) * 1000
		offsets.append(offset_ms)
		unit = "beat" if duration_beats == 1 else "beats"
		print(
			f"Note {number:3d}: start={start:9.3f}s | end={end:9.3f}s | "
			f"end offset={offset_ms:+8.1f} ms from beat {grid_beat:3d} | "
			f"duration={duration_beats} {unit}"
		)

	if len(offsets):
		offsets_arr = np.asarray(offsets)
		abs_offsets = np.abs(offsets_arr)
		median_abs = float(np.median(abs_offsets))

		print("\n--- Timing & Synchronization Summary ---")
		print(f"Total Notes/Segments : {len(offsets)}")
		print(f"Mean End Offset      : {np.mean(offsets_arr):+.2f} ms")
		print(f"Median End Offset    : {np.median(offsets_arr):+.2f} ms")
		print(f"Std Deviation        : {np.std(offsets_arr):.2f} ms")
		print(f"Max Absolute Offset  : {np.max(abs_offsets):.2f} ms")

		# If offsets show intentional timing modulation (> 3 ms), display steganography analysis
		if median_abs > 3.0:
			binary_bits = "".join("1" if o > 0 else "0" for o in offsets_arr)
			nominal_targets = np.where(offsets_arr > 0, median_abs, -median_abs)
			jitter = np.abs(offsets_arr - nominal_targets)
			consistent_pct = np.mean(jitter <= 2.0) * 100

			print("\n--- Steganography Analysis ---")
			print(f"Detected Modulation  : ~+/-{median_abs:.1f} ms")
			print(f"Step Consistency     : {consistent_pct:.1f}% within +/ 	'-2.0 ms of target")
			print(f"Max Modulation Jitter: {np.max(jitter):.2f} ms")
			print(f"Extracted Bits: {binary_bits[:]}")
		else:
			print(f"Notes within +/-1 ms : {np.sum(abs_offsets <= 1.0)} / {len(offsets)} ({np.mean(abs_offsets <= 1.0)*100:.1f}%)")
			print(f"Notes within +/-2 ms : {np.sum(abs_offsets <= 2.0)} / {len(offsets)} ({np.mean(abs_offsets <= 2.0)*100:.1f}%)")


if __name__ == "__main__":
	main()
