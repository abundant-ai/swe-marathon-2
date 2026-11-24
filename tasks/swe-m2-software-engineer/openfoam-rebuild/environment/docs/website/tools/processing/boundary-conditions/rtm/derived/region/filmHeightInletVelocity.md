<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/region/filmHeightInletVelocity -->

# filmHeightInletVelocity

## Description

The `filmHeightInletVelocity` is boundary condition designed to be used in
conjunction with surface film modelling. It provides a velocity inlet boundary
condition for patches where the film height is specified. The inflow velocity is
obtained from the flux with a direction normal to the patch faces using:

up\=nϕρ∣Sf∣δ \\u\_p \= \\frac{\\vec{n} \\phi}{\\rho \|\\vec{S}\_f\| \\delta}up​\=ρ∣Sf​∣δnϕ​
where:

| Property | Description |
| --- | --- |
| up\\u\_pup​ | Patch velocity \[m/s] |
| n\\vec{n}n | Patch normal vector |
| ϕ\\phiϕ | Mass flux \[kg/s] |
| ρ\\rhoρ | Density \[kg/m^3] |
| Sf\\vec{S}\_fSf​ | Patch face area vectors \[m^2] |
| δ\\deltaδ | Film height \[m] |

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
    type            filmHeightInletVelocity;

    // Optional entries
    phi             <word>;
    rho             <word>;
    deltaf          <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `filmHeightInletVelocity` | word | yes | \- |
| `phi` | Name of flux field | word | yes | \- |
| `rho` | Name of density field | word | yes | \- |
| `deltaf` | Name of height field | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [filmHeightInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/surfaceFilmModels/derivedFvPatchFields/filmHeightInletVelocity)

API:

* [Foam::filmHeightInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_filmHeightInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
