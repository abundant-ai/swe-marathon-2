<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/surfaceFieldValue -->

# surfaceFieldValue

## Description

The `surfaceFieldValue` function object provides options to manipulate
surface field data into derived forms, e.g. to report summations, averages and
extrema; to calculate the volumetric or mass flux across a patch.

*Base* operations:

* `none` : no operation
* `min` : minimum
* `max` : maximum
* `sum` : summation
* `sumMag` : sum of magnitudes
* `sumDirection` :
* `sumDirectionBalance` :
* `average` : average
* `areaAverage` : area average
* `areaIntegrate` : area integral
* `CoV` : Coefficient of Variation
* `areaNormalAverage` : area\-normal average
* `areaNormalIntegrate` : area\-normal integral
* `uniformity` : uniformity index

*Weighted* operations:

* `weightedSum`
* `weightedAverage`
* `weightedAreaAverage`
* `weightedAreaIntegrate`
* `weightedUniformity`

*Absolute weighted* operations:

* `absWeightedSum`
* `absWeightedAverage`
* `absWeightedAreaAverage`
* `absWeightedAreaIntegrate`
* `absWeightedUniformity`

## Usage

Example of the `surfaceFieldValue` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
surfaceFieldValue1
{
    // Mandatory entries (unmodifiable)
    type            surfaceFieldValue;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields          (<field1> <field2> ... <fieldN>);
    operation       <operationType>;
    regionType      patch;
    name            <patch>;

    // Optional entries (runtime modifiable)
    postOperation   none;
    weightField     alpha1;
    scaleFactor     1.0;
    writeArea       false;
    surfaceFormat   none;

    // Optional (inherited) entries
    writeFields     false;
    scalingFactor   1.0;
    writePrecision  8;
    writeToFile     true;
    useUserTime     true;
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: surfaceFieldValue | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of operand fields | wordList | yes | \- |
| regionType | Face regionType: see below | word | yes | \- |
| name | Name for regionType | word | yes | \- |
| operation | Operation type: see below | word | yes | \- |
| postOperation | Post\-operation type: see below | word | no | none |
| weightField | Name of field to apply weighting | word | no | none |
| scaleFactor | Output value scaling factor | scalar | no | 1\.0 |
| writeArea | Write the surface area | bool | no | false |
| surfaceFormat | Output value format | word | conditional on writeFields | none |

The inherited entries are elaborated in:

* [fieldValue](fieldValue.md)

Options for the `regionType` entry:

```
faceZone              | The `name` entry to specify the faceZone
patch                 | The `name` entry to specify the patch
functionObjectSurface | The `name` entry to specify a polySurface
sampledSurface        | A `sampledSurfaceDict` sub-dictionary and `name`

```

Options for the `operation` entry:

```
none          | no operation
min           | minimum
max           | maximum
sum           | sum
sumMag        | sum of component magnitudes
sumDirection  | sum values that are positive in given direction
sumDirectionBalance | sum of balance of values in given direction
average       | ensemble average
areaAverage   | area-weighted average
areaIntegrate | area integral
CoV           | coefficient of variation: standard deviation/mean
areaNormalAverage | area-weighted average in face normal direction
areaNormalIntegrate | area-weighted integral in face normal directon
uniformity    | uniformity index
weightedSum           | weighted sum
weightedAverage       | weighted average
weightedAreaAverage   | weighted area average
weightedAreaIntegrate | weighted area integral
weightedUniformity    | weighted uniformity index
absWeightedSum           | sum using absolute weighting
absWeightedAverage       | average using absolute weighting
absWeightedAreaAverage   | area average using absolute weighting
absWeightedAreaIntegrate | area integral using absolute weighting
absWeightedUniformity    | uniformity index using absolute weighting

```

Options for the `postOperation` entry:

```
none          | No additional operation after calculation
mag           | Component-wise `mag()` after normal operation
sqrt          | Component-wise `sqrt()` after normal operation

```

Usage by the `postProcess` utility is not available.

### Notes on entries

* The values reported by the `areaNormalAverage` and `areaNormalIntegrate`
operations are written as the first component of a field with the same
rank as the input field.
* Faces on empty patches get ignored.
* If the field is a volField the `faceZone` can only consist of boundary faces.
* Using `functionObjectSurface`:
	+ The keyword `subRegion` should not be used to select surfaces.

```
Instead specify the `regionType functionObjectSurface` and provide the name.

```

* Using `sampledSurface`:
	+ not available for surface fields
	+ if `interpolate=true` they use `interpolationCellPoint` otherwise they use

```
cell values

```

* each triangle in `sampledSurface` is logically only in one cell

```
so interpolation will be wrong when triangles are larger than
cells.  This can only happen for sampling on a `triSurfaceMesh`

```

* take care when using isoSurfaces \- these might have duplicate

```
triangles and so integration might be wrong

```

Uniformity:

UI(ϕ)\=1−12ϕ‾A∫∣Wϕ⋅n^−Wˉϕˉ∣dA ,  ϕˉ\=∫Wϕ⋅dA∫W⋅dAUI(\\phi) \= 1 \- \\frac{1}{2 \\overline{\\phi} A}
\\int{\\left\| W \\phi \\cdot \\hat{n} \- \\bar{W} \\bar{\\phi}\\right\| d\\vec{A}}
\\,,\\;
\\bar{\\phi} \= \\frac{\\int{W \\phi \\cdot d\\vec{A}}}{\\int{W \\cdot d\\vec{A}}}UI(ϕ)\=1−2ϕ​A1​∫​Wϕ⋅n^−Wˉϕˉ​​dA,ϕˉ​\=∫W⋅dA∫Wϕ⋅dA​
A velocity uniformity index is calculated with no weighting (W\=1\) and
ϕ\=u\\phi \= \\uϕ\=u.

A scalar concentration uniformity index is calculated with either
ρu\\rho \\uρu or u\\uu for weighting and ϕ\=conc\\phi \= concϕ\=conc.

## Sample output

Data is written to file

```
$FOAM_CASE/postProcessing/<function object>/<start time>/surfaceFieldValue.dat

```

An example of a typical output is given below:

```
# Area           : 1.2500000000e-03
# Scale factor   : 1.0000000000e+00
# Time                  weightedAverage(H2O)    weightedAverage(T)
0.01                    9.9999967766e-03        4.7103661930e+02
0.02                    9.9999999984e-03        4.7138303908e+02
0.03                    1.0000000000e-02        4.7183514514e+02
0.04                    1.0000000000e-02        4.7224152840e+02
0.05                    1.0000000032e-02        4.7252916359e+02
0.06                    1.0000076331e-02        4.7287719550e+02
0.07                    1.0013972934e-02        4.7510153455e+02

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `<operation-type>(<region-name>, <field-name>)` : result, e.g.
the sum of `phi` on patch `myPatch`: `sum(myPatch,phi)`

## Further information

Tutorial:

* [reactingParcelFoam](../../../processing/solvers/rtm/lagrangian-particle/reactingParcelFoam.md)
`verticalChannel` tutorial:
[verticalChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/verticalChannel)

Source code:

* [surfaceFieldValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldValues/surfaceFieldValue)

API:

* [Foam::functionObjects::fieldValues::surfaceFieldValue](https://api.openfoam.com/2606/Foam_functionObjects_fieldValues_surfaceFieldValue.html)

Related:

* [volFieldValue](volFieldValue.md) function object
* [fieldValueDelta](../../../../index.md#function-objects-field-fieldvaluedelta) function
object

**History:** Introduced in version [1\.7\.0](https://www.openfoam.com/news/main-news/openfoam-1.7.0) ]
