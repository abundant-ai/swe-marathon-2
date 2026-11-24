"""Create and run one file-backed rotor for testing a Jazzy hardware plugin."""

import argparse
import mmap
from pathlib import Path
import struct
from time import monotonic_ns, sleep


def run(directory):
    """Truncate demonstration endpoints on startup and exchange plant frames."""
    directory.mkdir(parents=True, exist_ok=True)
    measurement = directory / 'device.bin'
    command = directory / 'command.bin'
    measurement.write_bytes(bytes(64))
    command.write_bytes(bytes(64))
    print(f'device_file={measurement} command_file={command}', flush=True)
    generation = 1
    sequence = 0
    position = velocity = applied = 0.0
    with measurement.open('r+b') as sample_file, command.open('r+b') as command_file:
        with mmap.mmap(sample_file.fileno(), 64) as out, mmap.mmap(command_file.fileno(), 64) as incoming:
            try:
                while True:
                    first, = struct.unpack_from('<Q', incoming)
                    target_generation, _, mode, target, _, _, _ = struct.unpack_from('<QQQdQQQ', incoming, 8)
                    last, = struct.unpack_from('<Q', incoming)
                    applied = -4 * velocity
                    if first != 0 and first == last and first % 2 == 0 and target_generation == generation:
                        if mode == 1:
                            applied = 16 * (target - position) - 6 * velocity
                        elif mode == 2:
                            applied = target
                    velocity += 0.005 * applied
                    position += 0.005 * velocity
                    sequence += 2
                    struct.pack_into('<Q', out, 0, sequence - 1)
                    struct.pack_into('<QQQdddQ', out, 8, generation, monotonic_ns(), 1, position, velocity, applied, 0)
                    struct.pack_into('<Q', out, 0, sequence)
                    sleep(0.005)
            except KeyboardInterrupt:
                return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    run(parser.parse_args().directory)
