DEBUG = True

SAMPLE_RATE  = 44100
BPM = 600
D0 = 158                # Echo delay for bit 0 (in samples, non-harmonic)
D1 = 215                # Echo delay for bit 1 (in samples, non-harmonic)
D2 = 285                # Echo delay for symbol 2 (start of character marker, non-harmonic)
ALPHA = 0.3               # Echo volume (attenuation factor)
FRAME_LEN = 2*1024      # Audio chunk size per bit (L)
NOISE_THRESHOLD = 0.05  # Avoid noise triggering D2 (0.04)
K = FRAME_LEN//30       # Transition smoothing length

PRINT_EVERYTHING = False# Receiver.py, whether to print every binary received (may break with \n and special characters)

# Musical note frequencies (in Hz)
NOTES = {
    "G3": 196.00, "G#3": 207.65, "A3": 220.00, "Bb3": 233.08, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13, "E4": 329.63,
    "F4": 349.23, "F#4": 369.99, "G4": 392.00, "G#4": 415.30, "A4": 440.00,
    "Bb4": 466.16, "B4": 493.88, "C5": 523.25, "C#5": 554.37, "D5": 587.33,
    "D#5": 622.25, "E5": 659.25, "F5": 698.46, "F#5": 739.99, "G5": 783.99,
    "G#5": 830.61, "A5": 880.00, "Bb5": 932.33, "B5": 987.77, "C6": 1046.50,
    "ULTRA": 19500
}

# BPM = 600
MARIO = [
    # --- Introdução ---
    ("E5", 1), (None, 1), ("E5", 1), (None, 2), ("E5", 1), (None, 2),
    ("C5", 1), (None, 1), ("E5", 2), (None, 1),
    ("G5", 4), (None, 4),
    ("G4", 4), (None, 4),

    # --- Seção A ---
    ("C5", 2), (None, 2), ("G4", 2), (None, 2), ("E4", 2), (None, 2),
    ("A4", 2), (None, 1), ("B4", 2), (None, 1),
    ("Bb4", 1), (None, 1), ("A4", 2), (None, 1),
    ("G4", 2), ("E5", 2), ("G5", 2),
    ("A5", 2), (None, 1), ("F5", 1), ("G5", 1), (None, 1),
    ("E5", 2), (None, 1), ("C5", 1), ("D5", 1), ("B4", 2), (None, 2),

    # --- Seção A (repetição) ---
    ("C5", 2), (None, 2), ("G4", 2), (None, 2), ("E4", 2), (None, 2),
    ("A4", 2), (None, 1), ("B4", 2), (None, 1),
    ("Bb4", 1), (None, 1), ("A4", 2), (None, 1),
    ("G4", 2), ("E5", 2), ("G5", 2),
    ("A5", 2), (None, 1), ("F5", 1), ("G5", 1), (None, 1),
    ("E5", 2), (None, 1), ("C5", 1), ("D5", 1), ("B4", 2), (None, 2),

    # --- Seção B ---
    ("G5", 1), ("F#5", 1), ("F5", 1), ("D#5", 2), (None, 1), ("E5", 2), (None, 1),
    ("G#4", 1), ("A4", 1), ("C5", 1), (None, 1), ("A4", 1), ("C5", 1), ("D5", 1), (None, 2),
    ("G5", 1), ("F#5", 1), ("F5", 1), ("D#5", 2), (None, 1), ("E5", 2), (None, 1),
    ("C6", 2), (None, 1), ("C6", 1), ("C6", 2), (None, 4),

    ("G5", 1), ("F#5", 1), ("F5", 1), ("D#5", 2), (None, 1), ("E5", 2), (None, 1),
    ("G#4", 1), ("A4", 1), ("C5", 1), (None, 1), ("A4", 1), ("C5", 1), ("D5", 1), (None, 2),
    ("D#5", 3), (None, 1), ("D5", 3), (None, 1),
    ("C5", 4), (None, 4),
]

# BPM = 300
LOOPING = [
    ("A3", 2), ("C4", 1), ("D4", 1), ("E4", 2), ("D4", 1), ("C4", 1),
    ("D4", 2), ("E4", 1), ("C4", 1), ("A3", 3), (None, 1),
    ("A3", 2), ("C4", 1), ("D4", 1), ("E4", 2), ("G4", 1), ("A4", 1),
    ("G4", 2), ("E4", 1), ("D4", 1), ("E4", 3), (None, 1),
    ("A4", 2), ("G4", 1), ("E4", 1), ("D4", 2), ("E4", 1), ("G4", 1),
    ("A4", 2), ("G4", 1), ("E4", 1), ("D4", 3), (None, 1),
    ("E4", 2), ("D4", 1), ("C4", 1), ("A3", 2), ("G3", 1), ("A3", 1),
    ("C4", 2), ("D4", 2), ("E4", 1), ("D4", 1), ("C4", 1), ("G3", 1),
]

UNIFORM = [("B4", 4)]
ULTRASOUND = [("ULTRA", 4)]


