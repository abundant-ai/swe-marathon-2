<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/gradientEnergy -->

# gradientEnergy

## Description

The `gradientEnergy` is a boundary condition that provides
a gradient condition for internal energy.

The gradient is calculated using:

∇(ep)\=∇⊥Cp(p,T)\+ep−ecΔ \\nabla(e\_p) \= \\nabla\_\\perp C\_p(p, T) \+ \\frac{e\_p \- e\_c}{\\Delta}∇(ep​)\=∇⊥​Cp​(p,T)\+Δep​−ec​​
where:

| Property | Description |
| --- | --- |
| epe\_pep​ | Energy at patch faces \[J] |
| ece\_cec​ | Energy at patch internal cells \[J] |
| ppp | Pressure \[bar] |
| TTT | Temperature \[K] |
| CpC\_pCp​ | Specific heat \[J/kg/K] |
| Δ\\DeltaΔ | Distance between patch face and internal cell centres \[m] |

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
    type            gradientEnergy;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `gradientEnergy` \` | word | yes | \- |

The inherited entries are elaborated in:

* fixedGradientFvPatchField.H

## Further information

Tutorial:

* [contaminatedDroplet2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/contaminatedDroplet2D)

Source code:

* [gradientEnergy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/basic/derivedFvPatchFields/gradientEnergy)

API:

* [Foam::gradientEnergyFvPatchScalarField](https://api.openfoam.com/2606/Foam_gradientEnergyFvPatchScalarField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
