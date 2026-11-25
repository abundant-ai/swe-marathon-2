<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/activeBaffleVelocity -->

# activeBaffleVelocity

## Description

The `activeBaffleVelocity` is a velocity boundary condition that simulates the
opening of a baffle due to local flow conditions, by merging the behaviours of
`wall` and `cyclic` conditions. The baffle joins two mesh regions, where the
open fraction determines the interpolation weights applied to each cyclic\- and
neighbour\-patch contribution.

We determine whether the baffle is opening or closing from the sign of
the net force across the baffle, from which the baffle open fraction is
updated using:

x\=xold\+sign(Fnet)ΔtT x \= x\_{old} \+ \\text{sign}(\\vec{F}\_{net}) \\frac{\\Delta t}{T}x\=xold​\+sign(Fnet​)TΔt​
where:

| Property | Description |
| --- | --- |
| xxx | Baffle open fraction \[0\-1] |
| xoldx\_{old}xold​ | Baffle open fraction on previous evaluation \[0\-1] |
| Δt\\Delta tΔt | Simulation time step \[s] |
| TTT | Time taken to open the baffle \[s] |
| Fnet\\vec{F}\_{net}Fnet​ | Net force across the baffle \[N] |

The open fraction is then applied to scale the patch areas.

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
    type                  activeBaffleVelocity;
    cyclicPatch           <word>;
    orientation           <label>;
    openFraction          <scalar>;
    openingTime           <scalar>;
    maxOpenFractionDelta  <scalar>;

    // Optional entries
    p                     <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `activeBaffleVelocity` | word | yes | \- |
| `cyclicPatch` | Name of cyclic patch | word | yes | \- |
| `orientation` | Flag to switch flow direction, either 1 or \-1 | label | yes | \- |
| `openFraction` | Current open fraction of patch \[0\-1] | scalar | yes | \- |
| `openingTime` | Time taken to open the baffle | scalar | yes | \- |
| `maxOpenFractionDelta` | Max open fraction change per timestep | scalar | yes | \- |
| `p` | Name of pressure field | word | no | `p` |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [activeBaffleVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/activeBaffleVelocity)

API:

* [Foam::activeBaffleVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_activeBaffleVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
