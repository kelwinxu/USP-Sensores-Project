import numpy as np
import constants as c

def text_to_bits(text):
    """Convert each character of the text into an 8-bit binary string."""
    bits = ""                               # Empty buffer to store bits
    for char in text:                       # For each caracter
        ascii_code = ord(char)              # Gets its ascii_code
        binary = format(ascii_code, "08b")  # Convert to binary
        bits += "2" + binary                # Add to the buffer (with '2' as start marker)
    return bits

def generate_melody(notes):
    """Synthesize the musical notes into a single audio array."""
    seconds_per_beat = 60.0 / c.BPM
    audio_parts = []                        # Stores each played note

    for note, beats in notes:
        duration = beats * seconds_per_beat
        num_samples = int(round(duration * c.SAMPLE_RATE))

        if note is None:
            # Musical rest (silence)
            wave_data = np.zeros(num_samples)
        else:
            freq = c.NOTES[note]                                    # Search for the frequency in NOTES
            t = np.arange(num_samples) / c.SAMPLE_RATE              # Creates a timeline in seconds for each note
            if note == "ULTRA" or freq * 2 >= c.SAMPLE_RATE / 2:
                # Pure sine wave for ultrasound to prevent harmonic aliasing into audible frequencies
                wave_data = 0.5 * np.sin(2.0 * np.pi * freq * t)
            else:
                wave_data = 0.25 * (np.sin(2.0 * np.pi * freq * t)      # sin wave with 35% intensity
                + 0.5 * np.sin(2.0 * np.pi * freq*2 * t)
                + 0.25 * np.sin(2.0 * np.pi * freq*3 * t))  

            # Fade in and fade out (5ms) to avoid clicking sounds
            fade_samples = int(0.005 * c.SAMPLE_RATE)               # How many samples is in 5ms
            if num_samples > 2 * fade_samples:                      # If there is space for fading in the note (at least 10ms)
                fade_in = np.linspace(0.0, 1.0, fade_samples)       # Fade in ramp
                fade_out = np.linspace(1.0, 0.0, fade_samples)      # Fade out ramp
                wave_data[:fade_samples] *= fade_in                 # Apply fade in on the note (start to fade_samples 5ms)
                wave_data[-fade_samples:] *= fade_out               # Apply fade out on the note (end-5ms to end)

        audio_parts.append(wave_data)       # Append to the played notes array

    audio = np.concatenate(audio_parts)     # Makes it a single continuous array

    # Add subtle background noise so the echo works even during silent rests
    noise = np.random.normal(0.0, 0.004, size=len(audio))
    return audio + noise

def create_chunk_mixer(prev_symbol, curr_symbol, target_symbol, frame_len=c.FRAME_LEN, k=c.K):
    """Generates 1 chunk (frame) with a smooth transition using a cosine curve over the first K samples."""
    if prev_symbol == target_symbol: prev_val = 1.0
    else: prev_val = 0.0
    if curr_symbol == target_symbol: curr_val = 1.0
    else: curr_val = 0.0

    mix = np.full(frame_len, curr_val, dtype=float)
    if prev_val != curr_val:
        # S curve (Cos) from 0.0 to 1.0
        curva_cosseno = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, k)))
        mix[:k] = prev_val + (curr_val - prev_val) * curva_cosseno

    return mix


def create_mixer_signal(bits, frame_len, target_symbol):
    """Generate whole signal by joining chunks"""
    chunks = []
    for i, curr_symbol in enumerate(bits):
        # No primeiro bit (i == 0), assume que o anterior era igual para nao criar rampa a toa
        if i > 0: prev_symbol = bits[i - 1]
        else: prev_symbol = curr_symbol
        bloco = create_chunk_mixer(prev_symbol, curr_symbol, target_symbol, frame_len)
        chunks.append(bloco)

    return np.concatenate(chunks)

def analyze_frame(frame):
    """Calculate Real Cepstrum and return echo strengths at D0, D1, and D2."""

    
    # Real Cepstrum: Re(IFFT(ln(|FFT(x)| + eps)))
    windowed = frame * np.hanning(len(frame))   # Hann
    spec = np.abs(np.fft.fft(windowed))
    log_spec = np.log(spec + 1e-12)
    rceps = np.real(np.fft.ifft(log_spec))

    # Take maximum in a small neighborhood (+/- 1 sample) to handle air/mic jitter
    c0 = np.max(rceps[c.D0 - 1 : c.D0 + 2])
    c1 = np.max(rceps[c.D1 - 1 : c.D1 + 2])
    c2 = np.max(rceps[c.D2 - 1 : c.D2 + 2])

    return c0, c1, c2

def classify_symbol(frame, noise_threshold=0.0):
    """Retorns '0', '1' or '2' based on frame's highest peak."""
    c0, c1, c2 = analyze_frame(frame)
    if c2 >= c0 and c2 >= c1 and (c2 - max(c0, c1)) >= noise_threshold:
        return "2", c2
    elif c1 >= c0:
        return "1", c1
    else:
        return "0", c0


def classify_bit(frame):
    """classify_symbol, but for data 0 or 1"""
    b0, b1, _ = analyze_frame(frame)
    if b1 > b0: return "1"
    else: return "0"


def bits_to_char(bit_str, printable_only=False):
    """Sanitiza uma string de 8 bits e converte para caractere ASCII."""
    clean_bits = ""
    for b in bit_str:
        if b == "1":
            clean_bits += "1"
        else:
            clean_bits += "0"

    ascii_code = int(clean_bits, 2) # binary
    if printable_only and not (32 <= ascii_code <= 126):
        return "?"
    return chr(ascii_code)

def melody_length(melody):
    len = 0
    for _, note in melody:
        len += note
    return len