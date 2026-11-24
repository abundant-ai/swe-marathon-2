<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/activeBaffleVelocity -->

# activeBaffleVelocity

## Description

The `activeBaffleVelocity` is a velocity boundary condition that simulates the
opening of a baffle due to local flow conditions, by merging the behaviours of
wall and cyclic conditions. The baffle joins two mesh regions, where the open
fraction determines the interpolation weights applied to each cyclic\- and
neighbour\-patch contribution.

## Usage

The condition requires entries in both the `boundary` and field files.

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
    type            activeBaffleVelocity;
    cyclicPatch     <word>;
    orientation     <label>;
    openFraction    <scalar>;
    openingTime     <scalar>;
    maxOpenFractionDelta <scalar>;

    // Optional entries
    p               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `activeBaffleVelocity` | word | yes | \- |
| `cyclicPatch` | Name of cyclic patch used when the active baffle is open | word | yes | \- |
| `orientation` | Orientation (1 or \-1\) of the active baffle patch | label | yes | \- |
| `openFraction` | Current fraction of the active baffle which is open | scalar | yes | \- |
| `openingTime` | Time taken for the active baffle to open | scalar | yes | \- |
| `maxOpenFractionDelta` | Maximum fractional change to the active baffle openness per time step | scalar | yes | \- |
| `p` | Name of pressure field | word | no | p |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* The `orientation` is used to change the direction of opening without the need for
reordering the patch faces.

## Method

It is determined whether the baffle is opening or closing from the sign of
the net force across the baffle, from which the baffle open fraction is
updated using:

x\=xold\+sign(Fnet)dtDT x \= x\_{old} \+ sign(F\_{net})\\frac{dt}{DT}x\=xold​\+sign(Fnet​)DTdt​
where:

| Property | Description |
| --- | --- |
| xxx | Baffle open fraction \[0\-1] |
| xoldx\_{old}xold​ | Baffle open fraction on previous evaluation |
| dtdtdt | Simulation time step |
| DTDTDT | Time taken to open the baffle |
| FnetF\_{net}Fnet​ | Net force across the baffle |

The open fraction is then applied to scale the patch areas.

## Further information

Tutorial:

* N/A

Source code:

* [activeBaffleVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/activeBaffleVelocity)

API:

* [Foam::activeBaffleVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_activeBaffleVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
