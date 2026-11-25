<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/STDMD -->

# STDMD

## Description

The `STDMD` function object implements Streaming Total Dynamic Mode
Decomposition (STDMD) based on an algorithm developed by Kiewat (2019\), Hemati
et al. (2017\), and Hemati et al. (2014\).

`STDMD` can compute the dominant modes of a given flow (or dataset), each of
which is associated with a constant frequency and decay rate, so that dynamic
features of a given flow may become interpretable, and tractable.
Among other Dynamic Mode Decomposition (DMD) variants, `STDMD` is presumed
to provide the general DMD method capabilities alongside economised and
feasible memory and CPU usage.

The code implementation corresponds to Figs. 15\-16 of the first citation
below, more broadly to Section 2\.4\.

### References

```
STDMD and mode-sorting algorithms (tags:K, HRDC, KZ, HWR):
    Kiewat, M. (2019).
    Streaming modal decomposition approaches for vehicle aerodynamics.
    PhD thesis. Munich: Technical University of Munich.
    URL:mediatum.ub.tum.de/doc/1482652/1482652.pdf

    Hemati, M. S., Rowley, C. W., Deem, E. A., & Cattafesta, L. N. (2017).
    De-biasing the dynamic mode decomposition for applied Koopman
    spectral analysis of noisy datasets.
    Theoretical and Computational Fluid Dynamics, 31(4), 349-368.
    DOI:10.1007/s00162-017-0432-2

    Kou, J., & Zhang, W. (2017).
    An improved criterion to select dominant modes from dynamic mode
    decomposition.
    European Journal of Mechanics-B/Fluids, 62, 109-129.
    DOI:10.1016/j.euromechflu.2016.11.015

    Hemati, M. S., Williams, M. O., & Rowley, C. W. (2014).
    Dynamic mode decomposition for large and streaming datasets.
    Physics of Fluids, 26(11), 111701.
    DOI:10.1063/1.4901016

Parallel classical Gram-Schmidt process (tag:Ka):
    Katagiri, T. (2003).
    Performance evaluation of parallel Gram-Schmidt re-orthogonalization
    methods.
    In: Palma J. M. L. M., Sousa A. A., Dongarra J., Hernández V. (eds)
    High Performance Computing for Computational Science — VECPAR 2002.
    Lecture Notes in Computer Science, vol 2565, p. 302-314.
    Berlin, Heidelberg: Springer.
    DOI:10.1007/3-540-36569-9_19

Parallel direct tall-skinny QR decomposition (tags:BGD, DGHL):
    Benson, A. R., Gleich, D. F., & Demmel, J. (2013).
    Direct QR factorizations for tall-and-skinny matrices in MapReduce
    architectures.
    2013 IEEE International Conference on Big Data.
    DOI:10.1109/bigdata.2013.6691583

    Demmel, J., Grigori, L., Hoemmen, M., & Langou, J. (2012).
    Communication-optimal parallel and sequential QR and LU
    factorizations.
    SIAM Journal on Scientific Computing, 34(1), A206-A239.
    DOI:10.1137/080731992

DMD properties:
    Brunton S. L. (2018).
    Dynamic mode decomposition overview.
    Seattle, Washington: University of Washington.
    youtu.be/sQvrK8AGCAo (Retrieved:24-04-20)

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>(s)` |
| output field | volScalarField(s) | `$FOAM_CASE/<time>/<outField>(s)` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

Output fields:

```
modeReal<modeIndex><field> | Real part of a mode field
modeImag<modeIndex><field> | Imaginary part of a mode field

```

Output files:

```
uSTDMD.dat                 | Unfiltered STDMD output
STDMD.dat                  | Filtered STDMD output

```

The following quantities are written for each mode:

```
Frequency
Magnitude
Amplitude (real part)
Amplitude (imaginary part)
Eigenvalue (real part)
Eigenvalue (imaginary part)

```

## Usage

Example of the `STDMD` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
STDMD1
{
    // Mandatory entries (unmodifiable)
    type                STDMD;
    libs                (fieldFunctionObjects);
    field               <inpField>;

    // Conditional mandatory entries (unmodifiable)
    // either of the below
    stdmdInterval       5.5;
    executeInterval     10;

    // Optional entries (unmodifiable)
    modeSorter          kiewat;
    nModes              50;
    maxRank             50;
    nGramSchmidt        5;
    fMin                0;
    fMax                1000000000;

    // Optional entries (run-time modifiable, yet not recommended)
    testEigen           false;
    dumpEigen           false;
    minBasis            0.00000001;
    minEVal             0.00000001;
    absTol              0.001;
    relTol              0.0001;
    sortLimiter         500;

    // Optional (inherited) entries
    writePrecision  8;
    writeToFile     true;
    useUserTime     true;
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries are defined below:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: STDMD | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| stdmdInterval | STDMD time\-step size \[s] | scalar | conditional | executeInterval\*(current time\-step of the simulation) |
| modeSorter | Mode\-sorting algorithm variant | word | no | firstSnap |
| nModes | Number of output modes in input freq range | label | no | GREAT |
| maxRank | Max columns in accumulated matrices | label | no | GREAT |
| nGramSchmidt | Number of Gram\-Schmidt iterations | label | no | 5 |
| fMin | Min (non\-negative) output frequency | label | no | 0 |
| fMax | Max output frequency | label | no | GREAT |
| testEigen | Flag to verify eigendecompositions | bool | no | false |
| dumpEigen | Flag to log operands of eigendecomps | bool | no | false |
| minBasis | Orthogonal basis expansion threshold | scalar | no | 1e\-8 |
| minEVal | Min EVal for below EVals are omitted | scalar | no | 1e\-8 |
| absTol | Min abs tol in eigendecomposition tests | scalar | no | 1e\-4 |
| relTol | Relative tol in eigendecomposition tests | scalar | no | 1e\-6 |
| sortLimiter | Maximum allowable magnitude for mag(eigenvalue)\*(number of STDMD steps) to be used in modeSorter\={kiewat,kouZhang} to avoid overflow errors | scalar | no | 500\.0 |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Options for the `modeSorter` entry:

```
kiewat    | Modified weighted amplitude scaling method
kouZhang  | Weighted amplitude scaling method
firstSnap | Method of first snapshot amplitude magnitude

```

Usage by `postProcess` utility is not available.

### Notes on entries

* To specify the `STDMD` time\-step size (not necessarily equal to the
time step of the simulation), entries of either `stdmdInterval` or
`executeInterval` must be available (highest to lowest precedence). While
`stdmdInterval` allows users to directly specify the `STDMD` time\-step size
in seconds, in absence of `stdmdInterval`, for convenience,
`executeInterval` allows users to compute the `STDMD` time\-step internally
by multiplying itself with the current time\-step size of the simulation.
* Limitation: Restart is currently not available since intermediate writing
of `STDMD` matrices are not supported.
* Limitation: Non\-physical input (e.g. full\-zero fields) may upset `STDMD`.
* Warning: DMD is an active research area at the time of writing; therefore,
there would be cases whereat oddities might be encountered.
* Warning: This `STDMD` release is the `beta` release; therefore,
small\-to\-medium changes in input/output interfaces and internal structures
should be expected in the next versions.
* Warning: In `modeSorter` algorithms of `kiewat` and `kouZhang`, there
exists a function of `power(x,y)` where `x` is the magnitude of an
eigenvalue, and `y` is the number of `STDMD` snapshots. This function poses
a risk of overflow errors since, for example, if `x` ends up above 1\.5 with
500 snapshots or more, this function automatically throws the floating point
error meaning overflow. Therefore, the domain\-range of this function is
heuristically constrained by the optional entry `sortLimiter` which skips
the evaluation of this function for a given
`mag(eigenvalue)*(no. of STDMD steps)`, i.e. `x*y`, whose magnitude is larger
than `sortLimiter`.

Example by using the `postProcess` utility:

```
<solver> -postProcess -fields '(U p)' -time '10:'

```

Note that the utility reads the DMD settings from `system/controlDict.functions`

## Sample output

## Further information

Tutorial:

* [cylinder2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/cylinder2D)

Source code:

* [STDMD](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/DMD/DMDModels/derived/STDMD)

API:

* [Foam::DMDModels::STDMD](https://api.openfoam.com/2606/Foam_DMDModels_STDMD.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
