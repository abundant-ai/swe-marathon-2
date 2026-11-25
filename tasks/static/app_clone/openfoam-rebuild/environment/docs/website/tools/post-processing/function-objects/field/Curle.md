<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/Curle -->

# Curle

## Description

The `Curle` function object computes the acoustic
pressure based on Curle's analogy.

Curle's analogy is implemented as:

p′\=14πr∣r∣2⋅(F∣r∣\+1c0dFdt) p' \= \\frac{1}{4 \\pi}
 \\frac{\\vec{r}}{\| \\vec{r} \| ^2} \\cdot
 \\left(
 \\frac{\\vec{F}}{\| \\vec{r} \|}
 \+ \\frac{1}{c\_0}\\frac{d\\vec{F}}{dt}
 \\right)p′\=4π1​∣r∣2r​⋅(∣r∣F​\+c0​1​dtdF​)
where:

p′p'p′
: Curle's acoustic pressure \[Pa] or \[Pa (m3/kg)]

c0c\_0c0​
: Reference speed of sound \[m/s]

r\\vec{r}r
: Distance vector to observer locations \[m]

F\\vec{F}F
: Force \[N] or \[N (m3/kg)]

ttt
: Time \[s]

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file 1 | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output file 2 | surface file | `$FOAM_CASE/<outputDir>/<time>/<surfaceName>` |
| output field | \- | \- |

## Usage

Example of the `Curle` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
Curle1
{
    // Mandatory entries (unmodifiable)
    type            Curle;
    libs            (fieldFunctionObjects);
    input           <point|surface>;
    output          <point|surface>;
    patches         (<patch1> <patch2> ... <patchN>);
    c0              343;

    // Conditional mandatory entries (runtime modifiable)
    // if input=point
    observerPositions    (<point1> <point2> ... <pointN>);

    // if input=surface
    surface              <surfaceFileName>;    // "inputSurface.obj";

    // if output=surface
    surfaceType          <surfaceType>;        // ensight;
    formatOptions
    {
        vtk
        {
            format  ascii;
        }
    }

    // Optional entries (runtime modifiable)
    p               p;

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
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: Curle | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| patches | Sound generation patch names | wordList | yes | \- |
| c0 | Reference speed of sound | scalar | yes | \- |
| input | Input type | word | yes | \- |
| output | Output type | word | yes | \- |
| p | Pressure field name | word | no | p |
| observerPositions | List of observer positions (x y z) | pointList | conditional | \- |
| surface | Input surface file name | word | conditional | \- |
| surfaceType | Output surface type | word | conditional | \- |
| formatOptions | Dictionary of surface format options | dictionary | conditional | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Options for the `input` and `output` entries:

```
point   | Operand is a set of points
surface | Operand is a surface

```

Usage by the `postProcess` utility is not available.

### Notes on entries

* Only the normal\-pressure force is included in the force calculation.

## Further information

Tutorial:

* [vortexShed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/vortexShed)

Source code:

* [Curle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/Curle)

API:

* [Foam::functionObjects::Curle](https://api.openfoam.com/2606/Foam_functionObjects_Curle.html)

**History:** Introduced in version [v1706](https://www.openfoam.com/news/main-news/openfoam-v1706)
