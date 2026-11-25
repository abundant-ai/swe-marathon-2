<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/advective -->

# advective

## Description

The `advective` is a general boundary condition to simulate non\-reflecting
advective outflow condition, based on solving the material derivative of
the given field on the boundary.

The material derivative is solved for a given field:

DϕDt≈∂ϕ∂t\+Un⋅∂ϕ∂n\=0\\frac{D \\phi}{D t}
\\approx
\\frac{\\partial \\phi}{\\partial t} \+ U\_n \\cdot \\frac{\\partial \\phi}{\\partial \\mathbf{n}}
\=
0DtDϕ​≈∂t∂ϕ​\+Un​⋅∂n∂ϕ​\=0
where:

| Property | Description |
| --- | --- |
| ϕ\\phiϕ | Field |
| UnU\_nUn​ | Advection velocity component normal to boundary |
| n\\mathbf{n}n | Outward\-pointing unit boundary\-normal vector |

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
    type            advective;

    // Optional entries
    phi             <word>;
    rho             <word>;
    lInf            <scalar>;

    // Conditional entries

        // when lInf is given
        fieldInf    <Type>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `advective` | word | yes | \- |
| `phi` | Name of the flux transporting the field | word | no | phi |
| `rho` | Name of the density field used to normalise the mass flux | word | no | rho |
| `lInf` | Relaxation length\-scale | scalar | no | \-GREAT |
| `fieldInf` | Field value of the far\-field | Type | no | Zero |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

* The standard time schemes (`backward`, `Euler`, `CrankNicolson`, `localEuler`)
are supported.
* The relaxation length\-scale `lInf` and the far\-field value `fieldInf` are
to optionally relax the value at the boundary to a specified far\-field value.
* If `lInf` is specified, `fieldInf` will be required.
* `rho` is only required in the case of a mass\-based flux.
* The advection velocity is assumed to be normal to the boundary.

## Further information

Tutorial:

* [planeChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/planeChannel)

Source code:

* [advective](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/advective)

API:

* [Foam::advectiveFvPatchField](https://api.openfoam.com/2606/Foam_advectiveFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
