<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/delta/rtm/cubeRootVol -->

# Cube\-root volume

## Properties

* Good representation for isotropic hexahedral meshes
* Less valid when the cell aspect ratio is not 1

## Model equations

The length scale is given by:

Δ\=c(Vc)13 \\Delta \= c \\left( V\_c \\right)^{\\frac{1}{3}}Δ\=c(Vc​)31​
where `c` is a model coefficient.

## Usage

The model is specified using:

```
delta           cubeRootVol;

cubeRootVolCoeffs
{
    // Optional entries

    // Multiplier
    deltaCoeff      1;
}

```

## Further information

Source code:

* [Foam::LESModels::cubeRootVolDelta](https://api.openfoam.com/2606/Foam_LESModels_cubeRootVolDelta.html)
