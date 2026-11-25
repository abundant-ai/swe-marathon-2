<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/heatTransferCoeff -->

# heatTransferCoeff

## Description

The `heatTransferCoeff` function object computes
the heat transfer coefficient as a `volScalarField` for a set of patches.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `heatTransferCoeff` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
heatTransferCoeff1
{
    // Mandatory entries (unmodifiable)
    type            heatTransferCoeff;
    libs            (fieldFunctionObjects);
    field           <field>;
    patches         (<patch1> <patch2> ... <patchN>);
    htcModel        <htcModel>;
    UInf            (20 0 0);
    Cp              CpInf;
    CpInf           1000;
    rho             rhoInf;
    rhoInf          1.2;

    // Optional (inherited) entries
    result          <fieldResult>;
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
| type | Type name: heatTransferCoeff | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| patches | Names of the operand patches | wordList | yes | \- |
| htcModel | Model for coefficient computation | word | yes | \- |
| UInf | Reference flow speed | scalar | yes | \- |
| rho | Fluid density | scalar | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "heatTransferCoeff(<field>)"

```

The following options are available for the `htcModel` entry:

* `ReynoldsAnalogy`: Reynolds analogy

h\=0\.5ρ∞Cp,∞∣U∞∣Cfh \= 0\.5 \\rho\_\\infty C\_{p,\\infty} \|U\_{\\infty}\| C\_fh\=0\.5ρ∞​Cp,∞​∣U∞​∣Cf​

* `localReferenceTemperature`: local reference temperature

h\=qTc−Twh \= \\frac{q}{T\_c \- T\_w}h\=Tc​−Tw​q​

* `fixedReferenceTemperature`: fixed reference temperature

h\=qTc−Trefh \= \\frac{q}{T\_c \- T\_{\\ref}}h\=Tc​−Tref​q​

## Further information

Source code:

* [heatTransferCoeff](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/heatTransferCoeff)

API:

* [Foam::functionObjects::heatTransferCoeff](https://api.openfoam.com/2606/Foam_functionObjects_heatTransferCoeff.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
