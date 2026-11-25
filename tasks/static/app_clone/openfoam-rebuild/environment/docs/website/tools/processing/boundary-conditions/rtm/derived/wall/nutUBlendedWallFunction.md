<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutUBlendedWallFunction -->

# nutUBlendedWallFunction

## Description

The `nutUBlendedWallFunction` is boundary condition that provides
a wall function for the turbulent
viscosity (i.e. `nut`) based on velocity (i.e. `U`) using a
binomial\-function wall\-function blending method between the viscous
and inertial sublayer predictions of \\c nut for low\- and high\-Reynolds
number applications.

uτ\=(uτ,visn\+uτ,logn)1/n u\_\\tau \= (u\_{\\tau,vis}^n \+ u\_{\\tau,log}^n)^{1/n}uτ​\=(uτ,visn​\+uτ,logn​)1/n
where:

| Property | Description |
| --- | --- |
| uτu\_\\tauuτ​ | Friction velocity |
| uτ,visu\_{\\tau,vis}uτ,vis​ | Friction velocity in the viscous sublayer |
| uτ,logu\_{\\tau,log}uτ,log​ | Friction velocity in the inertial sublayer |

#### References

* See the section that describes 'automatic wall treatment':

```
Menter, F., Ferreira, J. C., Esch, T., Konno, B. (2003).
The SST turbulence model with improved wall treatment
for heat transfer predictions in gas turbines.
In Proceedings of the International Gas Turbine Congress.
November, 2003. Tokyo, Japan. pp. 2-7.

```

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
    type            nutUBlendedWallFunction;

    // Optional entries
    n               4.0;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutUBlendedWallFunction` | word | yes | \- |
| `n` | Blending type | scalar | no | 4\.0 |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H

* The full 'automatic wall treatment' description also requires use of the
\\link omegaWallFunctionFvPatchScalarField.H with the \\c blending
option `binomial` or with the deprecated `blended` flag set to `on`.
* Suffers from non\-exact restart since `correctNut()` (called through
`turbulence->validate`) returns a slightly different value every time
it is called. See `nutUSpaldingWallFunctionFvPatchScalarField.C`.

## Further information

Tutorial:

* [backwardFacingStep2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/backwardFacingStep2D)

Source code:

* [nutUBlendedWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutUBlendedWallFunction)

API:

* [Foam::nutUBlendedWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutUBlendedWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
