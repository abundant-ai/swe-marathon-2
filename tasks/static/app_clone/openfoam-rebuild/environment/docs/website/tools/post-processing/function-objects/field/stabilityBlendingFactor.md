<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/stabilityBlendingFactor -->

# stabilityBlendingFactor

## Description

The `stabilityBlendingFactor` function object
computes the `stabilityBlendingFactor` to be used by the
local blended convection scheme. The output is a surface field weight
between 0\-1\.

The weight of a blended scheme, i.e. `w`, is given by a function of
the blending factor, `f`:

w\=fscheme1\+(1−fscheme2) w \= f\_{scheme\_1} \+ (1 \- f\_{scheme\_2})w\=fscheme1​​\+(1−fscheme2​​)
The factor is calculated based on six criteria:

1. mesh non\-orthogonality field
2. magnitude of cell centres gradient
3. convergence rate of residuals
4. faceWeight
5. skewness
6. Courant number

The user can enable them individually.

For option 1, the following relation is used, where ϕ1\\phi\_1ϕ1​ is
the non\-orthogonality:

fNon\=min(max(0\.0,(ϕ1−max(ϕ1))/(min(ϕ1)−max(ϕ1))),1\.0)fNon \=
 min
 (
 max
 (
 0\.0,
 (\\phi\_1 \- max(\\phi\_1\))
 /(min(\\phi\_1\) \- max(\\phi\_1\))
 ),
 1\.0
 )fNon\=min(max(0\.0,(ϕ1​−max(ϕ1​))/(min(ϕ1​)−max(ϕ1​))),1\.0)
For option 2, the following relation is used, where ϕ2\\phi\_2ϕ2​ is
the magnitude of cell centres gradient (Note that ϕ2\=3\\phi\_2 \= 3ϕ2​\=3
for orthogonal meshes):

fMagGradCc\=min(max(0\.0,(ϕ2−max(ϕ2))/(min(ϕ2)−max(ϕ2))),1\.0)fMagGradCc \=
 min
 (
 max
 (
 0\.0,
 (\\phi\_2 \- max(\\phi\_2\))
 / (min(\\phi\_2\) \- max(\\phi\_2\))
 ),
 1\.0
 )fMagGradCc\=min(max(0\.0,(ϕ2​−max(ϕ2​))/(min(ϕ2​)−max(ϕ2​))),1\.0)
For option 3, a PID control is used in order to control residual
unbounded fluctuations for individual cells.

factor\=P∗residual\+I∗residualIntegral\+D∗residualDifferentialfactor \=
 P\*residual
 \+ I\*residualIntegral
 \+ D\*residualDifferentialfactor\=P∗residual\+I∗residualIntegral\+D∗residualDifferential
where `P`, `I` and `D` are user inputs.

The following relation is used:

fRes\=(factor−meanRes)/(maxRes∗meanRes); fRes \= (factor \- meanRes)/(maxRes\*meanRes);fRes\=(factor−meanRes)/(maxRes∗meanRes);
where

meanResmeanResmeanRes
: Average(residual)

maxResmaxResmaxRes
: User input

Note that fResf\_{Res}fRes​ will blend more towards one as
the cell residual is larger then the domain mean residuals.

For option 4, the following relation is used, where ϕ4\\phi\_4ϕ4​ is
the face weight (Note that ϕ4\=0\.5\\phi\_4 \= 0\.5ϕ4​\=0\.5 for orthogonal meshes):

ffaceWeight\=min(max(0\.0,(min(ϕ4)−ϕ4)/(min(ϕ4)−max(ϕ4))),1\.0) ffaceWeight \= min
 (
 max
 (
 0\.0,
 (min(\\phi\_4\) \- \\phi\_4\)
 / (min(\\phi\_4\) \- max(\\phi\_4\))
 ),
 1\.0
 )ffaceWeight\=min(max(0\.0,(min(ϕ4​)−ϕ4​)/(min(ϕ4​)−max(ϕ4​))),1\.0)
For option 5, the following relation is used, where ϕ5\\phi\_5ϕ5​ is
the cell skewness:

fskewness\=min(max(0\.0,(ϕ5−max(ϕ5))/(min(ϕ5)−max(ϕ5))),1\.0) fskewness \=
 min
 (
 max
 (
 0\.0,
 (\\phi\_5 \- max(\\phi\_5\))
 / (min(\\phi\_5\) \- max(\\phi\_5\))
 ),
 1\.0
 )fskewness\=min(max(0\.0,(ϕ5​−max(ϕ5​))/(min(ϕ5​)−max(ϕ5​))),1\.0)
For option 6, the following relation is used:

fCoWeight\=min(max((Co−Co1)/(Co2−Co1),0),1) fCoWeight \= min(max((Co \- Co1\)/(Co2 \- Co1\), 0\), 1\)fCoWeight\=min(max((Co−Co1)/(Co2−Co1),0),1)
where

Co1
: Courant number below which scheme2 is used

Co2
: Courant number above which scheme1 is used

The final factor is determined by:

f\=max(fNon,fMagGradCc,fRes,ffaceWeight,fskewness,fCoWeight) f \= max(fNon, fMagGradCc, fRes, ffaceWeight, fskewness, fCoWeight)f\=max(fNon,fMagGradCc,fRes,ffaceWeight,fskewness,fCoWeight)
An indicator (volume) field, named `blendedIndicator` is generated if the log
flag is on:

1
: represent scheme1 as active,

0
: represent scheme2 as active.

Additional reporting is written to the standard output, providing
statistics as to the number of cells used by each scheme.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `stabilityBlendingFactor` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
stabilityBlendingFactor1
{
    // Mandatory entries (unmodifiable)
    type                 stabilityBlendingFactor;
    libs                 (fieldFunctionObjects);

    // Mandatory entries (unmodifiable)
    field               <field>;    // U;
    result              <outField>; // UBlendingFactor;

    // Optional entries (runtime modifiable)
    tolerance           0.001;

    // Any of the options can be chosen in combinations

    // Option-1
    switchNonOrtho      true;
    nonOrthogonality    nonOrthoAngle;
    maxNonOrthogonality 20;
    minNonOrthogonality 60;

    // Option-2
    switchGradCc        true;
    maxGradCc           3;
    minGradCc           4;

    // Option-3
    switchResiduals     true;
    maxResidual         10;
    residual            initialResidual:p;
    P                   1.5;
    I                   0;
    D                   0.5;

    // Option-4
    switchFaceWeight    true;
    maxFaceWeight       0.3;
    minFaceWeight       0.2;

    // Option-5
    switchSkewness      true;
    maxSkewness         2;
    minSkewness         3;

    // Option-6
    switchCo            true;
    U                   U;
    Co1                 1;
    Co2                 10;

    // Optional (inherited) entries
    writePrecision      8;
    writeToFile         true;
    useUserTime         true;
    region              region0;
    enabled             true;
    log                 true;
    timeStart           0;
    timeEnd             1000;
    executeControl      timeStep;
    executeInterval     1;
    writeControl        timeStep;
    writeInterval       1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: stabilityBlendingFactor | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| result | Name of surface field used in the localBlended scheme | word | yes | \- |
| switchNonOrtho | Select non\-orthogonal method | bool | no | false |
| nonOrthogonality | Name of the non\-orthogonal field | word | no | nonOrthoAngle |
| maxNonOrthogonality | Maximum non\-orthogonal for scheme2 | scalar | no | 20 |
| minNonOrthogonality | Minimum non\-orthogonal for scheme1 | scalar | no | 60 |
| switchGradCc | Select cell centre gradient method | bool | no | false |
| maxGradCc | Maximum gradient for scheme2 | scalar | no | 2 |
| minGradCc | Minimum gradient for scheme1 | scalar | no | 4 |
| switchResiduals | Select residual evolution method | bool | no | false |
| residual | Name of the residual field | word | no | initialResidual:p |
| maxResidual | Maximum residual\-mean ratio for scheme1 | scalar | no | 10 |
| P | Proportional factor for PID | scalar | no | 3 |
| I | Integral factor for PID | scalar | no | 0 |
| D | Differential factor for PID | scalar | no | 0\.25 |
| switchFaceWeight | Select face weight method | bool | no | false |
| faceWeight | Name of the faceWeight field | word | no | faceWeight |
| maxFaceWeight | Maximum face weight for scheme1 | scalar | no | 0\.2 |
| minFaceWeight | Minimum face weight for scheme2 | scalar | no | 0\.3 |
| switchSkewness | Select skewness method | bool | no | false |
| skewness | Name of the skewness field | word | no | skewness |
| maxSkewness | Maximum skewness for scheme2 | scalar | no | 2 |
| minSkewness | Minimum skewness for scheme1 | scalar | no | 3 |
| switchCo | Select Co blended method | bool | no | false |
| U | Name of the flux field for Co blended | word | no | U |
| Co1 | Courant number below which scheme2 is used | scalar | no | 1 |
| Co2 | Courant number above which scheme1 is used | scalar | no | 10 |
| tolerance | Tolerance for number of blended cells | scalar | no | 0\.001 |

The `result` entry is the field which is read by the `localBlended` scheme
specified in `fvSchemes`. This name is determined by the `localBlended` class.

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [motorBike](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/LES/motorBike/motorBike)

Source code:

* [stabilityBlendingFactor](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/stabilityBlendingFactor)

API:

* [Foam::functionObjects::stabilityBlendingFactor](https://api.openfoam.com/2606/Foam_functionObjects_stabilityBlendingFactor.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
