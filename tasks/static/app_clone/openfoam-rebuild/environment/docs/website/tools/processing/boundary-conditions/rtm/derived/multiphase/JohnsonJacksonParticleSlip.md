<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/JohnsonJacksonParticleSlip -->

# JohnsonJacksonParticleSlip

## Description

The `JohnsonJacksonParticleSlip` is a boundary condition that provides
partial slip boundary condition for the particulate velocity.

#### References

```
Reuge, N., Cadoret, L., Coufort-Saudejaud, C.,
Pannala, S., Syamlal, M., & Caussat, B. (2008).
Multifluid Eulerian modeling of dense gas–solids fluidized bed
hydrodynamics: influence of the dissipation parameters.
Chemical Engineering Science, 63(22), 5540-5551.

Johnson, P. C., & Jackson, R. (1987).
Frictional–collisional constitutive relations for granular materials,
with application to plane shearing.

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
    type            JohnsonJacksonParticleSlip;
    specularityCoefficient  <dimensionedScalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `JohnsonJacksonParticleSlip` | word | yes | \- |
| `specularityCoefficient` | Specularity coefficient \[\-] | dimensionedScalar | yes | \- |

The inherited entries are elaborated in:

* partialSlipFvPatchFields.H

* The specularity coefficient has to be within (0, 1\).

## Further information

Tutorial:

* [LBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/RAS/LBend)

Source code:

* [JohnsonJacksonParticleSlip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/twoPhaseEuler/phaseCompressibleTurbulenceModels/kineticTheoryModels/derivedFvPatchFields/JohnsonJacksonParticleSlip)

API:

* [Foam::JohnsonJacksonParticleSlipFvPatchVectorField](https://api.openfoam.com/2606/Foam_JohnsonJacksonParticleSlipFvPatchVectorField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
