<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/uniformTotalPressure -->

# uniformTotalPressure

## Description

The `uniformTotalPressure` is a boundary condition that provides
provides a time\-varying form of the uniform total pressure boundary condition
`totalPressure`.

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
    type            uniformTotalPressure;
    p0              <Function1<scalar>>;

    // Optional entries
    U               <word>;
    psi             <word>;
    rho             <word>;
    phi             <word>;

    // Conditional entries

        // if 'psi' is not 'none'
        gamma       <scalar>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformTotalPressure` | word | yes | \- |
| `p0` | Total pressure field | Function1\<scalar\> | yes | \- |
| `U` | Name of velocity field | word | no | U |
| `psi` | Name of compressibility field | word | no | psi |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `gamma` | Heat\-capacity ratio | scalar | conditional | 1 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* Function1\.H

## Further information

Tutorial:

* [TJunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunction)

Source code:

* [uniformTotalPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformTotalPressure)

API:

* [Foam::uniformTotalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_uniformTotalPressureFvPatchScalarField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
