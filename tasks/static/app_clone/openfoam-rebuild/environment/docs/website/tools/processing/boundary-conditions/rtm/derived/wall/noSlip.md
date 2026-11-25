<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/noSlip -->

# noSlip

## Description

The `noSlip` is a velocity boundary condition that fixes the velocity
to zero at walls.

up\=0 \\vec{u}\_p \= 0up​\=0
where:

| Property | Type |
| --- | --- |
| up\\vec{u}\_pup​ | Velocity at the boundary |

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            noSlip;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `noSlip` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [pitzDaily](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/potentialFoam/pitzDaily)
* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [noSlip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/noSlip)

API:

* [Foam::noSlipFvPatchVectorField](https://api.openfoam.com/2606/Foam_noSlipFvPatchVectorField.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
