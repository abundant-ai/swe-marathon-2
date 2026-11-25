<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/turbulentInlet -->

# turbulentInlet

## Description

The `turbulentInlet` is a boundary condition that produces spatiotemporal\-variant
field by summing a set of pseudo\-random numbers and a given spatiotemporal\-invariant
mean field. The field can be any type, e.g. `scalarField`. At a single point and
time, all components are summed by the same random number, e.g. velocity
components (u, v, w) are summed by the same random number, p; thus, output
is (u\+p, v\+p, w\+p).

The pseudo\-random number generator obeys the probability density function
of the uniform distribution constrained by the range \[0:1]. The seed for
the random number generator is hard\-coded; therefore, it will produce the
same sequence of random numbers at every execution.

xp\=(1−α)xpn−1\+α(xref\+csR∣xref∣) x\_p \= (1 \- \\alpha) x\_p^{n \- 1} \+ \\alpha (x\_{ref} \+ c s R \|x\_{ref}\|)xp​\=(1−α)xpn−1​\+α(xref​\+csR∣xref​∣)
where:

| Property | Description |
| --- | --- |
| xpx\_pxp​ | Patch field |
| xrefx\_{ref}xref​ | Spatiotemporal\-invariant patch scalar |
| nnn | Time level |
| α\\alphaα | A scalar attempting to build two\-temporal\-point correlations by heuristically adding a fraction of the new random component to the previous time patch field |
| ccc | A heuristic automatically calculated correction term to compensate energy level losses due to the alpha scalar |
| RRR | Pseudo\-random number \[HARD\-CODED seed] |
| sss | Fluctuation scale (proportional to the xRef) |

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type             patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type             turbulentInlet;
    fluctuationScale <scalar>;               // the term `s` above
    referenceField   <scalarField>;          // the term `xRef` above

    // Optional entries
    alpha            <scalar>;               // the term `alpha` above

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentInlet` | word | yes | \- |
| `fluctuationScale` | RMS fluctuation scale (fraction of mean) | scalar | yes | \- |
| `referenceField` | Reference (mean) field | scalarField | yes | \- |
| `alpha` | Fraction of new random component added to previous | scalar | no | 0\.1 |

The inherited entries are elaborated in:

* [fixedValueFvPatchField.H](../general/fixedValue.md)
* Random.H

* This boundary condition should not be used for DES or LES computations as a
turbulent velocity inflow condition, because the BC will not produce
turbulence\-alike time\-series, and will decay almost immediately downstream
of the inlet boundary although its historical name suggests the opposite.
* Nevertheless, the BC may be still used for other applications, e.g. as a
uniform\-random noise source in aeroacoustics.

## Further information

Tutorial:

* [pitzDaily](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/LES/pitzDaily)

Source code:

* [turbulentInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/turbulentInlet)

API:

* [Foam::turbulentInletFvPatchField](https://api.openfoam.com/2606/Foam_turbulentInletFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
