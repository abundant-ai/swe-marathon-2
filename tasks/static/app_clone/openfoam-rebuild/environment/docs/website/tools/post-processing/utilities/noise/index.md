<!-- https://doc.openfoam.com/2606/tools/post-processing/utilities/noise/ -->

# noise

The `noise` utility requires the [FFTW](https://www.fftw.org) library to compute
Discrete Fourier Transforms (DFTs). Building of the `noise` utility is
skipped if the [FFTW](https://www.fftw.org) library was not found during OpenFOAM
installation.

## Overview

The `noise` utility processes [point](pointNoise.md) and [surface](surfaceNoise.md)
pressure data to generate:

* Root Mean Square (RMS) pressure \[Pa];
* Sound Pressure Level (SPL) \[dB];
* Power Spectral Density (PSD) in \[Pa2^22/Hz] and/or \[dB/Hz]; and
* 1/3 Octave SPL data, whereby the bins are constrained to pass through the
centre frequency at 1 kHz.

Input data can be windowed using a run\-time selectable model, where options
include:

* Uniform;
* Hanning, with options including symmetry, and extended (non\-zero at the
end\-points); and
* window overlap.

## Usage

Command line usage:

noteOption lists are generated from `noise -help` in a sourced OpenFOAM environment. Run `npm run refresh-help-snippets` to update the snippet below.

```
Usage: noise [OPTIONS]
  -help  Display short help and exit

```

The `noise` utility is configured using a `<case>/system/noiseDict` taking the
general form:

```
noiseModel      <modelType>

<modelType>Coeffs
{
    // Model-specific entries (see below)
    // `````````````````````````````````~

    ...

    // Common entries
    // ````````````~~

    windowModel     Hanning;

    HanningCoeffs
    {
        // Window overlap percentage
        overlapPercent  50;
        symmetric       yes;
        extended        yes;

        // Optional number of windows, default = all available
        nWindow         5;
    }

    // Input files list
    files       ("postProcessing/faceSource1/surface/patch/patch.case";)

    // Optional entries
    // ```````````````~

    // Reference density (for incompressible cases); default = 1
    rhoRef      1;

    // Number of samples in sampling window; default = 2^16 (=65536)
    N               4096;

    // Lower frequency bound; default = 25 Hz
    fl              25;

    // Upper frequency bound; default = 10000 Hz
    fu              10000;

    // Start time
    startTime       1;

    // Minimum pressure
    minPressure     0;

    // Maximum pressure
    maxPressure     100000;

    // SPL weighting; default = none
    SPLweighting    dBA;

    // Reference for dB calculation; default = 2e-5
    dBRef           2e-5;

    // Output prefix; default = ""
    outputPrefix    "source1";

    // Write options
    writeOptions
    {
        writePrmsf      yes;
        writeSPL        yes;
        writePSD        yes;
        writePSDf       yes;
        writeOctaves    yes;
    }
}

```

## SPL Weighting

SPL data can be weighted using the `SPLweighting` entry, where options include:

* `dB` : no weighting
* `dBA` : [A weighting](index.md#A-weighting)
* `dBB` : [B weighting](index.md#B-weighting)
* `dBC` : [C weighting](index.md#C-weighting)
* `dBD` : [D weighting](index.md#D-weighting)

### A weighting

```
SPLweighting    dBA;

```

The gain is computed as:

A(f)\=20log⁡10(RA(f))−20log⁡10(RA(1000)),A(f) \= 20\\log\_{10}(R\_A(f)) \- 20 \\log\_{10}(R\_A(1000\)),A(f)\=20log10​(RA​(f))−20log10​(RA​(1000)),
where

RA(f)\=121942f4(f2\+20\.62)(f2\+107\.72)(f2\+739\.92)(f2\+121942).R\_A(f) \= \\frac{12194^2 f^4}{(f^2 \+ 20\.6^2\)\\sqrt{(f^2 \+ 107\.7^2\)(f^2 \+ 739\.9^2\)}(f^2 \+ 12194^2\)}.RA​(f)\=(f2\+20\.62)(f2\+107\.72)(f2\+739\.92)​(f2\+121942)121942f4​.
### B weighting

```
SPLweighting    dBB;

```

The gain is computed as:

B(f)\=20log⁡10(RB(f))−20log⁡10(RB(1000)),B(f) \= 20\\log\_{10}(R\_B(f)) \- 20 \\log\_{10}(R\_B(1000\)),B(f)\=20log10​(RB​(f))−20log10​(RB​(1000)),
where

RB(f)\=121942f3(f2\+20\.62)(f2\+158\.52)(f2\+121942).R\_B(f) \= \\frac{12194^2 f^3}{(f^2 \+ 20\.6^2\)\\sqrt{(f^2 \+ 158\.5^2\)}(f^2 \+ 12194^2\)}.RB​(f)\=(f2\+20\.62)(f2\+158\.52)​(f2\+121942)121942f3​.
### C weighting

```
SPLweighting    dBC;

```

The gain is computed as:

C(f)\=20log⁡10(RC(f))−20log⁡10(RC(1000)),C(f) \= 20\\log\_{10}(R\_C(f)) \- 20 \\log\_{10}(R\_C(1000\)),C(f)\=20log10​(RC​(f))−20log10​(RC​(1000)),
where

RC(f)\=121942f2(f2\+20\.62)(f2\+121942)R\_C(f) \= \\frac{12194^2 f^2}{(f^2 \+ 20\.6^2\)(f^2 \+ 12194^2\)}RC​(f)\=(f2\+20\.62)(f2\+121942)121942f2​
### D weighting

```
SPLweighting    dBD;

```

The gain is computed as:

D(f)\=20log⁡10(RD(f)),D(f) \= 20\\log\_{10}(R\_D(f)),D(f)\=20log10​(RD​(f)),
where

RD(f)\=f6\.8966888496476e−5h(f)(f2\+79919\.29)(f2\+1345600),R\_D(f) \= \\frac{f}{6\.8966888496476e\-5}\\sqrt{\\frac{h(f)}{(f^2 \+ 79919\.29\)(f^2 \+ 1345600\)}},RD​(f)\=6\.8966888496476e−5f​(f2\+79919\.29)(f2\+1345600)h(f)​​,
and

h(f)\=(1037918\.48−f2)2\+1080768\.16f2(9837328−f2)2\+11723776f2.h(f) \= \\frac{(1037918\.48 \- f^2\)^2 \+ 1080768\.16 f^2}{(9837328 \- f^2\)^2 \+ 11723776 f^2}.h(f)\=(9837328−f2)2\+11723776f2(1037918\.48−f2)2\+1080768\.16f2​.
## Output

All possible data is written by default. The `writeOptions` sub dictionary can
contains a list of boolean entries to select results individually.

```
// Write options
writeOptions
{
    writePrmsf      yes;
    writeSPL        yes;
    writePSD        yes;
    writePSDf       yes;
    writeOctaves    yes;
}

```

The plain text output files created by the [pointNoise](pointNoise.md) model and
the [surfaceNoise](surfaceNoise.md) model's surface averaged data include a
header section that provides case information, e.g. for the average surface RMS
pressure:

```
# f [Hz] vs P(f) [Pa]
# Lower frequency: 2.50000000e+01
# Upper frequency: 5.00000000e+01
# Window model  : Hanning
# Window number : 7
# Window samples: 128
# Window overlap %: 5.00000000e+01
# dBRef         : 2.00000000e-05
# Area average  : true
# Area sum      : 8.99999982e-02
# Number of faces: 400
# f                 P(f)

```

## Further information

Source code

* [noise](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/postProcessing/noise)

See also

* [pointNoise](pointNoise.md)
* [surfaceNoise](surfaceNoise.md)
* [Curle](../../function-objects/field/Curle.md) function object

Tutorials

* [vortexShed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/vortexShed)
