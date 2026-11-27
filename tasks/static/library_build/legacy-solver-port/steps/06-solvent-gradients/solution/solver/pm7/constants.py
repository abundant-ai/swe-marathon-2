"""Physical constants (MOPAC 'fpcref(1,:)', CODATA 2018 set) and element tables."""

import math

FPC_1 = 1.602176634  # elementary charge (1e-19 C)
FPC_2 = 14.399645478456
A0 = 0.529177210903  # Bohr radius, Angstrom
EV = 27.211386245988  # Hartree in eV
FPC_8 = 2.99792458e10  # speed of light, cm/s
FPC_9 = 23.060547830619029  # eV -> kcal/mol
PI = 3.14159265358979323846

SYMBOLS = {1: "H", 6: "C", 7: "N", 8: "O", 9: "F", 15: "P", 16: "S", 17: "Cl", 35: "Br"}
ATOMIC_NUMBER = {v.upper(): k for k, v in SYMBOLS.items()}

# trunc_1 / trunc_2 of MOPAC: smooth NDDO -> point-charge transition (l_feather, on for PM7)
TRUNC_1 = 7.0
TRUNC_2 = 0.22

# atomic masses used for the centre of mass of charged species (dipole origin)
MASS = {
    1: 1.0079,
    6: 12.011,
    7: 14.0067,
    8: 15.9994,
    9: 18.9984,
    15: 30.97376,
    16: 32.06,
    17: 35.453,
    35: 79.904,
}

# covalent radii used by the bonding / connectivity test (atom_radius_covalent)
