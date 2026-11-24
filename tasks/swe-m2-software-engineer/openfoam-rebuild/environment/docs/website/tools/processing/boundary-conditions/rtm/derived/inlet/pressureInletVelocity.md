<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/pressureInletVelocity -->

# pressureInletVelocity

## Description

The `pressureInletVelocity` is a velocity boundary condition where
the inflow velocity is obtained from the flux with a direction normal
to the patch faces.

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
    type           pressureInletVelocity;

    // Optional entries
    phi            <word>;
    rho            <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressureInletVelocity` | word | yes | \- |
| `phi` | Name of the flux field | word | no | phi |
| `rho` | Name of the density field | word | no | rho |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

* If reverse flow is possible or expected use the
`pressureInletOutletVelocity` condition instead.

## Further information

Tutorial:

* [helmholtzResonance](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/laminar/helmholtzResonance)

Source code:

* [pressureInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureInletVelocity)

API:

* [Foam::pressureInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
