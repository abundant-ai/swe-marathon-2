<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/delta/rtm/vanDriest/ -->

# Van Driest

## Properties

* Van Driest damping function
* Includes additional limiting
* Applied in the region up to y\+y^\+y\+ of 500

## Model equations

The Van Driest damping function is given by:

D\=1−exp⁡−y\+A\+ D \= 1 \- \\exp^\\frac{\-y^\+}{A^\+}D\=1−expA\+−y\+​
The final length scale is given by:

Δ\=min⁡(κyCsD,Δg) \\Delta \= \\min \\left( \\frac{\\kappa y}{C\_s} D , \\Delta\_g \\right)Δ\=min(Cs​κy​D,Δg​)
where Δg\\Delta\_gΔg​ is a geometric\-based delta function such as the
[cube\-root volume](../cubeRootVol.md) delta.

## Usage

The model is specified using:

```
delta           vanDriest;

vanDriestCoeffs
{
    delta           <geometricDelta>;

    // Optional entries
    kappa           0.41;
    Aplus           26;
    Cdelta          0.158;
    calcInterval    1;
}

```

The model requires the near wall distance yyy which can be costly to compute
for moving mesh cases. Here, the optional `calcInterval` entry can be used to
reduce the update frequency of the wall distance calculation at the expense of
increased modelling errors.

## Further information

Source code:

* [Foam::LESModels::cubeRootVolDelta](https://api.openfoam.com/2606/Foam_LESModels_cubeRootVolDelta.html)
