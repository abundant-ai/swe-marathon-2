<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/continuityError -->

# continuityError

## Description

The `continuityError` function object computes local, global and cumulative
continuity errors for a flux field.

Local continuity error, ϵlocal\\epsilon\_\\text{local}ϵlocal​:

ϵlocal\=Δt⟨∣x∣⟩ \\epsilon\_\\text{local} \= \\Delta\_t \\langle \|x\| \\rangleϵlocal​\=Δt​⟨∣x∣⟩
Global continuity error, ϵglobal\\epsilon\_\\text{global}ϵglobal​:

ϵglobal\=Δt⟨∣x∣⟩ \\epsilon\_\\text{global} \= \\Delta\_t \\langle \|x\| \\rangleϵglobal​\=Δt​⟨∣x∣⟩
Cumulative continuity, ϵcum\\epsilon\_\\text{cum}ϵcum​:

ϵcum\+\=ϵglobal \\epsilon\_\\text{cum} \+\= \\epsilon\_\\text{global}ϵcum​\+\=ϵglobal​
where
Δt\\Delta\_tΔt​
: Time\-step size

\<.\>\<.\>\<.\>
: Cell\-volume weighted average operator

xxx
: ∇⋅ϕ\\nabla \\cdot \\phi∇⋅ϕ

ϕ\\phiϕ
: Flux field

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `continuityError` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
continuityError1
{
    // Mandatory entries (unmodifiable)
    type            continuityError;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    phi             phi;

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
| type | Type name: continuityError | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| phi | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Example by using the `postProcess -func` utility:

```
postProcess -func "continuityError(<field1>, <field2>, ..., <fieldN>)"

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `local` : local continuity error
* `global` : global continuity error
* `cumulative` : cumulative continuity error

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [continuityError](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/continuityError)

API:

* [Foam::functionObjects::continuityError](https://api.openfoam.com/2606/Foam_functionObjects_continuityError.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
