<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/waveTransmissive -->

# waveTransmissive

## Description

The `waveTransmissive` is a general boundary condition that
provides a wave transmissive outflow condition, based on solving
DDt(W, field) \= 0 at the boundary, `W` is the wave velocity
and `field` is the field to which this boundary condition is applied.

The wave speed is calculated using:

wp\=ϕp∣Sf∣\+γψp w\_p \= \\frac{\\phi\_p}{\|\\vec{S}\_f\|} \+ \\sqrt{\\frac{\\gamma}{\\psi\_p}}wp​\=∣Sf​∣ϕp​​\+ψp​γ​​
where:

| Property | Description |
| --- | --- |
| wpw\_pwp​ | Patch wave speed |
| ϕp\\phi\_pϕp​ | Patch face flux |
| ψp\\psi\_pψp​ | Patch compressibility |
| Sf\\vec{S}\_fSf​ | Patch face area vector |
| γ\\gammaγ | Ratio of specific heats |

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
    type            waveTransmissive;
    gamma           <scalar>;

    // Optional entries
    psi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `waveTransmissive` | word | yes | \- |
| `gamma` | Ratio of specific heats | scalar | yes | \- |
| `psi` | Name of compressibility field | word | no | thermo:psi |

The inherited entries are elaborated in:

* [advective](advective.md)

## Further information

Tutorial:

* [prism](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/sonicFoam/RAS/prism)

Source code:

* [waveTransmissive](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/waveTransmissive)

API:

* [Foam::waveTransmissiveFvPatchField](https://api.openfoam.com/2606/Foam_waveTransmissiveFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
