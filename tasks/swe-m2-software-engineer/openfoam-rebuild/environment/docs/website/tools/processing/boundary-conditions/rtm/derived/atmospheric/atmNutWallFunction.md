<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmNutWallFunction -->

# atmNutWallFunction

## Description

The `atmNutWallFunction` is a boundary condition that provides
a wall constraint on the turbulent viscosity (i.e. `nut`) based on the
turbulent kinetic energy (i.e. `k`) and velocity (i.e. `U`) for atmospheric
boundary layer modelling.

The governing equation of the boundary condition:

τw\=Uu∗Uk∗ \\tau\_w \= {U^\*\_u} {U^\*\_k}τw​\=Uu∗​Uk∗​
with:

Uu∗\=κUwln(zp/z0) {U^\*\_u} \= \\frac{\\kappa U\_w}{ln(z\_p / z\_0\)}Uu∗​\=ln(zp​/z0​)κUw​​
Uk∗\=Cμ1/4k {U^\*\_k} \= C\_{\\mu}^{1/4} \\sqrt{k}Uk∗​\=Cμ1/4​k​
where:

| Property | Description |
| --- | --- |
| τw\\tau\_wτw​ | Wall shear stress |
| Uu∗U^\*\_uUu∗​ | Local friction velocity based on near\-ground velocity |
| Uk∗U^\*\_kUk∗​ | Local friction velocity based on near\-ground k |
| κ\\kappaκ | von Karman constant |
| UwU\_wUw​ | Near\-ground velocity |
| zpz\_pzp​ | Vertical coordinate |
| z0z\_0z0​ | Surface roughness length \[m] |
| CmuC\_muCm​u | Empirical model constant |
| kkk | Turbulent kinetic energy |

#### References

* Theoretical expressions (tags:RH, SBJM, SM):

```
Richards, P. J., & Hoxey, R. P. (1993).
Appropriate boundary conditions for computational wind
engineering models using the k-ε turbulence model.
In Computational Wind Engineering 1 (pp. 145-153).
DOI:10.1016/B978-0-444-81688-7.50018-8

Sørensen, N. N., Bechmann, A., Johansen, J., Myllerup, L.,
Botha, P., Vinther, S., & Nielsen, B. S. (2007).
Identification of severe wind conditions using
a Reynolds Averaged Navier-Stokes solver.
In Journal of Physics: Conference
series (Vol. 75, No. 1, p. 012053).
DOI:10.1088/1742-6596/75/1/012053

Sumner, J., & Masson, C. (2012).
k−ε simulations of the neutral atmospheric boundary layer:
analysis and correction of discretization errors on practical grids.
International journal for numerical
methods in fluids, 70(6), 724-741.
DOI:10.1002/fld.2709

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
    type            atmNutWallFunction;
    z0Min           <scalar>;
    z0              <PatchFunction1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmNutWallFunction` | word | yes | \- |
| `z0Min` | Minimum surface roughness length \[m] | scalar | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |

The inherited entries are elaborated in:

* nutkWallFunctionFvPatchScalarField.H
* PatchFunction1\.H

## Further information

Tutorial:

* N/A

Source code:

* [atmNutWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/wallFunctions/atmNutWallFunction)

API:

* [Foam::atmNutWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmNutWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
