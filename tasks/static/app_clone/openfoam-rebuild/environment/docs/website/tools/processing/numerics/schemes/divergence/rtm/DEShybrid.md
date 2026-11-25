<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/rtm/DEShybrid -->

# DES hybrid divergence scheme

Hybrid convection scheme of Travin et al. for hybrid RAS/LES calculations.

## Properties

* Blends two schemes based on local properties including
* wall distance
* velocity gradient
* eddy viscosity
* Originally developed for DES calculations to blend a low\-dissipative scheme,
e.g. [linear](linear.md), in the vorticity\-dominated, finely\-resolved regions
and a numerically more robust, e.g. [linearUpwind](linearUpwind.md),
convection scheme in irrotational or coarsely\-resolved regions.

## Usage

The scheme is specified using:

```
divSchemes
{
    default         none;
    div(phi,U)      Gauss DEShybrid
        linear                    // scheme 1
        linearUpwind grad(U)      // scheme 2
        delta                     // LES delta name, e.g. 'delta', 'hmax'
        0.65                      // CDES coefficient
        30                        // Reference velocity scale
        2                         // Reference length scale
        0                         // Minimum sigma limit (0-1)
        1                         // Maximum sigma limit (0-1)
        1.0e-03                   // Limiter of B function, typically 1e-03
        1.0;                      // nut limiter (if > 1, GAM extension is active)
}

```

## Further information

Source code:

* [DEShybrid](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/schemes/DEShybrid)

API:

* [Foam::DEShybrid](https://api.openfoam.com/2606/Foam_DEShybrid.html)

References:

* First published in *Travin et al.* [78](../../../../../../references.md#travin_physical_2000)
* Original publication contained a typo for C\_H3 constant. Corrected version

```
with minor changes for 2 lower limiters published in *Spalart et al.*
[@cite spalart_sensitivity_2012]

```
