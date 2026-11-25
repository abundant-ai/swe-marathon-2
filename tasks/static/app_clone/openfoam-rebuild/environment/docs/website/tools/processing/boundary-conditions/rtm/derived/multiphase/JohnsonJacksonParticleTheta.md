<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/JohnsonJacksonParticleTheta -->

# JohnsonJacksonParticleTheta

## Description

The `JohnsonJacksonParticleTheta` is a boundary condition that provides
Robin condition for the particulate granular temperature.

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
    type            JohnsonJacksonParticleTheta;
    specularityCoefficient  <dimensionedScalar>;
    restitutionCoefficient  <dimensionedScalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `JohnsonJacksonParticleTheta` | word | yes | \- |
| `specularityCoefficient` | Specularity coefficient \[\-] | dimensionedScalar | yes | \- |
| `restitutionCoefficient` | Restitution coefficient \[\-] | dimensionedScalar | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

* The specularity coefficient has to be within (0, 1\).
* The restitution coefficient has to be within (0, 1\).

## Further information

Tutorial:

* [LBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/RAS/LBend)

Source code:

* [JohnsonJacksonParticleTheta](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/twoPhaseEuler/phaseCompressibleTurbulenceModels/kineticTheoryModels/derivedFvPatchFields/JohnsonJacksonParticleTheta)

API:

* [Foam::JohnsonJacksonParticleThetaFvPatchScalarField](https://api.openfoam.com/2606/Foam_JohnsonJacksonParticleThetaFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
