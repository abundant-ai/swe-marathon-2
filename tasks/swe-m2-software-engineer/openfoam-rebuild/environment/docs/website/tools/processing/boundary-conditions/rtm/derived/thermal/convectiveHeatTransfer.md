<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/convectiveHeatTransfer -->

# convectiveHeatTransfer

## Description

The `convectiveHeatTransfer` is a boundary condition that
provides a convective heat transfer coefficient condition:

* If Re\>500000Re \> 500000Re\>500000:

hp\=0\.664Re0\.5Pr0\.333κpL h\_p \= \\frac{0\.664 \\mathrm{Re}^{0\.5} \\mathrm{Pr}^{0\.333} \\kappa\_p}{L}hp​\=L0\.664Re0\.5Pr0\.333κp​​
* Else:

hp\=0\.037Re0\.8Pr0\.333κpL h\_p \= \\frac{0\.037 \\mathrm{Re}^{0\.8} \\mathrm{Pr}^{0\.333} \\kappa\_p}{L}hp​\=L0\.037Re0\.8Pr0\.333κp​​
where:

| Property | Description |
| --- | --- |
| hph\_php​ | Patch convective heat transfer coefficient |
| Re\\mathrm{Re}Re | Reynolds number |
| Pr\\mathrm{Pr}Pr | Prandtl number |
| κp\\kappa\_pκp​ | Thermal conductivity |
| LLL | Length scale |

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
    type            convectiveHeatTransfer;
    L               <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `convectiveHeatTransfer` | word | yes | \- |
| `L` | Length scale | scalar | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [hotBoxes](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/hotBoxes)

Source code:

* [convectiveHeatTransfer](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/convectiveHeatTransfer)

API:

* [Foam::compressible::convectiveHeatTransferFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_convectiveHeatTransferFvPatchScalarField.html)

**History:** Introduced in version [2206](https://www.openfoam.com/news/main-news/openfoam-2206)
