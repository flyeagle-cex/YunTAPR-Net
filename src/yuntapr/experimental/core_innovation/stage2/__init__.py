"""Stage 2 scientific candidates. No optimizer, authorization or training runner."""

CHANNELS = ('B08', 'B09', 'B10', 'B11', 'B13', 'B15', 'B16')
OFFSETS = (60, 50, 40, 30, 20, 10)
# Explicit candidate T/RH levels: 850/700 hPa; researcher freeze still required.
MEE_KEYS = ('pwat', 'cape', 'temperature850', 'temperature700',
            'relative_humidity850', 'relative_humidity700',
            'u850', 'v850', 'u700', 'v700', 'ps')
