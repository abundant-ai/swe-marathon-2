<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/blendingFactor -->

# blendingFactor

## Description

The `blendingFactor` function object computes and stores the blending
coefficient employed by **blended**
[divergence schemes](../../../processing/numerics/schemes/divergence.md), giving an indicator as to
which of the schemes is active across the domain.

Blended schemes combine contributions from two schemes, i.e. ϕ1\\phi\_1ϕ1​
and ϕ2\\phi\_2ϕ2​, using a weight field, i.e. www, such that the
effective scheme value, i.e. ϕeff\\phi\_\\effϕeff​, is computed as follows:

ϕeff\=wϕ1\+(1−w)ϕ2 \\phi\_\\eff \= w \\phi\_1 \+ (1 \- w) \\phi\_2ϕeff​\=wϕ1​\+(1−w)ϕ2​
It follows that when w\=1w \= 1w\=1, the scheme reduces to
ϕeff\=ϕ1\\phi\_\\eff \= \\phi\_1ϕeff​\=ϕ1​; similarly, when w\=0w \= 0w\=0, the
scheme reduces to ϕeff\=ϕ2\\phi\_\\eff \= \\phi\_2ϕeff​\=ϕ2​.

The weight field, i.e. www, is surface field and converted to a volume
field for easier post\-processing by setting the cell value to one minus
the minimum of the face values:

wc\=1−min⁡∀i∈faces(wf,i) w\_c \= 1 \- \\min\_{\\forall i \\in \\mathrm{faces}}\\left(w\_{f,i}\\right)wc​\=1−∀i∈facesmin​(wf,i​)
This conversion leads to blending indicator field whose values mean:

```
0   =  scheme 0
1   =  scheme 1
0-1 =  a blend between scheme 0 and scheme 1

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | volScalarField | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `blendingFactor` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
blendingFactor1
{
    // Mandatory entries (unmodifiable)
    type            blendingFactor;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entry (runtime modifiable)
    field           <field>;

    // Optional entries (runtime modifiable)
    phi             phi;
    tolerance       0.001;

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
| type | Type name: blendingFactor | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| phi | Name of flux field | word | no | phi |
| tolerance | Tolerance for number of blended cells | scalar | no | 0\.001 |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

The `field` and `phi` entries are used to construct the scheme name to lookup
from the [fvSchemes](../../../../fundamentals/case-structure/fvschemes.md) dictionary, as:

```
div(phi,U)

```

The `tolerance` entry is used as a threshold when computing the number of cells
identified as using each scheme.
The `tolerance` entry must be in the range 0 to 1, excluding
the endpoints.

## Stored properties

### Fields

The blending factor is stored on the mesh database, using the default name:

```
blendingFactor(<field>)

```

The name can be overridden by using the `result` entry.

## Further information

Related:

* [Courant number blended scheme](../../../processing/numerics/schemes/divergence/rtm/CoBlended.md)

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [blendingFactor](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/blendingFactor)

API:

* [Foam::functionObjects::blendingFactor](https://api.openfoam.com/2606/Foam_functionObjects_blendingFactor.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
