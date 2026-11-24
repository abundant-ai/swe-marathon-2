<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldAverage -->

# fieldAverage

## Description

The `fieldAverage` function object computes ensemble\- and/or time\-based
field averages, with optional windowing, for a user\-specified selection of
volumetric and/or surface fields.

Fields are entered as a list of sub\-dictionaries, which indicate the type of
averages to perform, and can be updated during the calculation. The current
options include:

* `mean`: arithmetic mean

x‾\=1N∑i\=0Nxi \\overline{x} \= \\frac{1}{N}\\displaystyle\\sum\\limits\_{i\=0}^N x\_ix\=N1​i\=0∑N​xi​
* `prime2Mean`: prime\-squared mean

x′‾2\=1N∑i\=0N(xi−x‾)2 \\overline{x'}^2 \= \\frac{1}{N} \\displaystyle\\sum\\limits\_{i\=0}^N
 (x\_i \- \\overline{x})^2x′2\=N1​i\=0∑N​(xi​−x)2
* `base`: average over 'time', or 'iteration' (`N` in the above)
* `window`: optional averaging window, specified in 'base' units

Average field names are constructed by concatenating the base field with
the averaging type, e.g. when averaging field 'U', the name of resultant fields
becomes:

* arithmetic mean field, `UMean`
* prime\-squared field, `UPrime2Mean`

Note that averaging is performed per cell. If the mesh is moving, e.g.
a rotating body within a static outer mesh, cells in the rotating region will
sample different regions of space which may lead to unexpected/non\-continuous
field average
results.

Information regarding the number of averaging steps, and total averaging
time are written on a per\-field basis to the
`<functionObject name>Properties` dictionary, located in `<time>/uniform`.

When restarting form a previous calculation, the averaging is continuous or
may be restarted using the `restartOnRestart` option.

The averaging process may be restarted after each calculation output time
using the `restartOnOutput` option or restarted periodically using the
`periodicRestart` option and setting `restartPeriod` to the required
averaging period.

With the `subRegion` option, also supports fields on function object
surface output (e.g., `sampledSurfaces`).

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field(s)` | `$FOAM_CASE/<time>/<inpField>s` |
| output file | \- | \- |
| output field | `{vol,surface}<Type>Field(s)` | `$FOAM_CASE/<time>/<outField>s` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `fieldAverage` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
fieldAverage1
{
    // Mandatory entries (unmodifiable)
    type            fieldAverage;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields
    (
        <field name 1>
        {
            mean        <yes|no>;
            prime2Mean  <yes|no>;
            base        <time|iteration>;
            windowType   exact;
            window       10.0;
            windowName   <name>;
            allowRestart true;
        }
        ...
        <field name N>
        {
            mean        <yes|no>;
            prime2Mean  <yes|no>;
            base        <time|iter>;
       }
    );

    // Optional entries (runtime modifiable)
    restartOnRestart    false;
    restartOnOutput     false;
    periodicRestart     false;
    restartPeriod       0.002;

    // Optional (inherited) entries
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
| type | Type name: fieldAverage | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of the operand fields and averaging options | dict | yes | \- |
| restartOnRestart | Restart the averaging on restart | bool | no | false |
| restartOnOutput | Restart the averaging on output | bool | no | false |
| periodicRestart | Periodically restart the averaging | bool | no | false |
| restartPeriod | Periodic restart period | scalar | conditional | \- |
| restartTime | One\-shot reset of the averaging | scalar | no | GREAT |
| subRegion | Name for alternative objectRegistry | word | no | "" |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldAverageItem](fieldAverageItem.md)

Usage by the `postProcess` utility is not available.

## Stored properties

### Fields

Average fields are stored on the mesh database, using the default name
constructions:

```
<field>Mean
<field>Prime2Mean

```

These are written to the standard time directories according to the
[writeControl](../index.md#usage-run-time-control) setting.

## Further information

Tutorial:

* [pitzDaily](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/LES/pitzDaily)
* [throttle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/cavitatingFoam/LES/throttle)
* [freeSpacePeriodic](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/discreteMethods/dsmcFoam/freeSpacePeriodic)

Source code:

* [fieldAverage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldAverage)

API:

* [Foam::functionObjects::fieldAverage](https://api.openfoam.com/2606/Foam_functionObjects_fieldAverage.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
