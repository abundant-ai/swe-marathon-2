<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/fixedMeanOutletInlet -->

# fixedMeanOutletInlet

## Description

The `fixedMeanOutletInlet` is a general boundary condition that extrapolates
field to the patch using the near\-cell values and adjusts the distribution to
match the specified, optionally time\-varying, mean value. This extrapolated
field is applied as a `fixedValue` for outflow faces but `zeroGradient` is
applied to inflow faces.

This boundary condition can be applied to pressure when `inletOutlet` is
applied to the velocity so that a `zeroGradient` condition is applied to the
pressure at inflow faces where the velocity is specified to avoid an
unphysical over\-specification of the set of boundary conditions.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            fixedMeanOutletInlet;
    meanValue       <Function1<Type>>;

    // Optional entries
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedMeanOutletInlet` | word | yes | \- |
| `meanValue` | Mean value that the field is adjusted to maintain | Function1\<Type\> | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::outletInletFvPatchField](https://api.openfoam.com/2606/Foam_outletInletFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* N/A

Source code:

* [fixedMeanOutletInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedMeanOutletInlet)

API:

* [Foam::fixedMeanOutletInletFvPatchField](https://api.openfoam.com/2606/Foam_fixedMeanOutletInletFvPatchField.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
