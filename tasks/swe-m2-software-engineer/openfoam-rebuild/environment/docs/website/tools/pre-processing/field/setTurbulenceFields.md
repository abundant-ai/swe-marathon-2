<!-- https://doc.openfoam.com/2606/tools/pre-processing/field/setTurbulenceFields -->

# setTurbulenceFields

## Overview

The `setTurbulenceFields` utility applies a two\-step automatic initialisation
procedure for [RAS](../../processing/models/turbulence/ras.md) computations based on the work of
Manceau[45](../../../references.md#manceau_two_yyyy) to address slow or non\-convergence
attributed in the first O(10\) time steps and improve resulting predictions.

## Usage

### Synopsis

```
setTurbulenceFields [OPTIONS]

```

#### Examples

```
setTurbulenceFields -region region1

```

### Input

#### Arguments

No arguments required.
#### Options

```
-case <dir>       Case directory (instead of current directory)
  -decomposeParDict <file>
                    Alternative decomposePar dictionary file
  -dict <file>      Alternative setTurbulenceFieldsDict
  -parallel         Run in parallel
  -region <name>    Specify mesh region (default: region0)
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-compat      Display compatibility options and exit
  -help-full        Display full help and exit

```

#### Files

The `setTurbulenceFields` utility is configured using a
`<case>/system/setTurbulenceFieldsDict`, taking the form:

```
// Mandatory entries
uRef            17.55;

// Optional entries
initialiseU     true;
initialiseEpsilon true;
initialiseK     true;
initialiseOmega true;
initialiseR     true;
writeF          true;

kappa           0.41;
Cmu             0.09;
dPlusRef        15.0;

f               f;
U               U;
epsilon         epsilon;
k               k;
omega           omega;
R               R;

```

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `uRef` | Reference speed | scalar | yes | \- |
| `initialiseU` | Flag to initialise U | bool | no | false |
| `initialiseEpsilon` | Flag to initialise epsilon | bool | no | false |
| `initialiseK` | Flag to initialise k | bool | no | false |
| `initialiseOmega` | Flag to initialise omega | bool | no | false |
| `initialiseR` | Flag to initialise R | bool | no | false |
| `writeF` | Flag to write elliptic\-blending field, f | bool | no | false |
| `kappa` | von Karman constant | scalar | no | 0\.41 |
| `Cmu` | Empirical constant | scalar | no | 0\.09 |
| `dPlusRef` | Reference dPlus | scalar | no | 15 |
| `f` | Name of operand f field | word | no | f |
| `U` | Name of operand U field | word | no | U |
| `epsilon` | Name of operand epsilon field | word | no | epsilon |
| `k` | Name of operand k field | word | no | k |
| `omega` | Name of operand omega field | word | no | omega |
| `R` | Name of operand R field | word | no | R |

* Time that the utility applies to is determined by the
`startFrom` and `startTime` entries of the `controlDict`.
* The utility modifies near\-wall fields, hence can be more effective
for low\-Re mesh cases.

#### Fields

No field input required.

### Output

#### Logs

No log output.

#### Files

No file output.

#### Fields

| Property | Description | Path | Type |
| --- | --- | --- | --- |
| `U` | Velocity | `<case>/<time>/` | volVectorField |
| `nut` | Turbulence viscosity | `<case>/<time>/` | volScalarField |
| `epsilon` | Turbulence kinetic energy dissipation rate | `<case>/<time>/` | volScalarField |
| `k` | Turbulence kinetic energy | `<case>/<time>/` | volScalarField |
| `omega` | Specific dissipation rate | `<case>/<time>/` | volScalarField |
| `R` | Reynolds stress tensor | `<case>/<time>/` | volSymmScalarField |
| `f` | Elliptic blending factor | `<case>/<time>/` | volScalarField |

## Method

Equations 3, 6, 8\-13 and page 2 of Manceau[45](../../../references.md#manceau_two_yyyy).

## Further information

Tutorial:

* [planeChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/turbulenceModels/planeChannel)

Source code:

* [setTurbulenceFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/preProcessing/setTurbulenceFields)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
