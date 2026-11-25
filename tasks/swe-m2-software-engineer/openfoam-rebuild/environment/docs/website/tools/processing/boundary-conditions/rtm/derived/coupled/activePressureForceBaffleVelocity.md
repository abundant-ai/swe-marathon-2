<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/activePressureForceBaffleVelocity -->

# activePressureForceBaffleVelocity

## Description

The `activePressureForceBaffleVelocity` is a velocity boundary condition that
simulates the opening or closure of a baffle due to area averaged pressure or
force delta, between both sides of the baffle. This is achieved by merging the
behaviours of `wall` and `cyclic` baffles.

The baffle joins two mesh regions, where the open fraction determines
the interpolation weights applied to each cyclic\- and neighbour\-patch
contribution. This condition is meant to be used in an extra wall beyond
an existing cyclic patch pair.

The baffle is activated when the area weighted pressure difference between
master and slave patches is larger then `minThresholdValue`.

Once the threshold is crossed, the baffle is activated and continues to
open or close at a fixed rate using

x\=xold\+s ΔtT x \= x\_{old} \+ s \\, \\frac{\\Delta t}{T}x\=xold​\+sTΔt​
where:

| Property | Description |
| --- | --- |
| xxx | Baffle open fraction \[0\-1] |
| xoldx\_{old}xold​ | Baffle open fraction on previous evaluation \[0\-1] |
| Δt\\Delta tΔt | Simulation time step \[s] |
| TTT | Time taken to open the baffle \[s] |
| sss | Sign for orientation: 1 to open or \-1 to close |

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
    type                  activePressureForceBaffleVelocity;
    cyclicPatch           <word>;
    orientation           <label>;
    openFraction          <scalar>;
    openingTime           <scalar>;
    maxOpenFractionDelta  <scalar>;
    minThresholdValue     <scalar>;
    forceBased            <bool>;
    opening               <bool>;

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
| `minThresholdValue` | Min absolute pressure or force difference for activation | scalar | yes | \- |
| `forceBased` | Force (true) or pressure\-based (false) activation | bool | yes | \- |
| `opening` | Baffle is opening (true) or closing (false) | bool | yes | \- |
| `p` | Name of pressure field | word | no | `p` |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [flamePropagationWithObstacles](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/PDRFoam/flamePropagationWithObstacles)

Source code:

* [activePressureForceBaffleVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/activePressureForceBaffleVelocity)

API:

* [Foam::activePressureForceBaffleVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_activePressureForceBaffleVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
