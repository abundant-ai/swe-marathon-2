<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wave/waveMaker -->

# waveMaker

## Description

The `waveMaker` is a boundary condition that provides
a point motion boundary condition to generate waves based on either piston
or flap motions.

#### Reference

```
Hughes, S.A. (1993).
Physical Models And Laboratory Techniques In Coastal Engineering.
Advanced Series On Ocean Engineering, volume 7.

```

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
    type            waveMaker;
    motionType      <word>;
    n               <vector>;
    initialDepth    <scalar>;
    wavePeriod      <scalar>;
    waveHeight      <scalar>;
    wavePhase       <scalar>;
    rampTime        <scalar>;

    // Optional entries
    waveAngle       <scalar>;
    startTime       <scalar>;
    secondOrder     <bool>;
    nPaddle         <label>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `waveMaker` | word | yes | \- |
| `motionType` | Motion type | word | yes | \- |
| `n` | Direction of motion | vector | yes | \- |
| `initialDepth` | Initial depth | scalar | yes | \- |
| `wavePeriod` | Wave period | scalar | yes | \- |
| `waveHeight` | Wave height | scalar | yes | \- |
| `wavePhase` | Wave phase | scalar | yes | \- |
| `rampTime` | Time to reach maximum motion | scalar | yes | \- |
| `waveAngle` | Wave angle | scalar | no | 0 |
| `startTime` | Start time | scalar | no | case start time |
| `secondOrder` | Second order calculation | bool | no | false |
| `nPaddle` | Number of paddles | label | no | 1 |

Options for the `motionType` entry:

| Property | Description |
| --- | --- |
| `piston` | Piston type |
| `flap` | Flap type |
| `solitary` | Solitary type |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

## Further information

Tutorial:

* [waveMakerFlap](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/waveMakerFlap)

Source code:

* [waveMaker](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/waveModels/derivedPointPatchFields/waveMaker)

API:

* [Foam::waveMakerPointPatchVectorField](https://api.openfoam.com/2606/Foam_waveMakerPointPatchVectorField.html)

**History:** Introduced in version [v1812](https://www.openfoam.com/news/main-news/openfoam-v1812)
