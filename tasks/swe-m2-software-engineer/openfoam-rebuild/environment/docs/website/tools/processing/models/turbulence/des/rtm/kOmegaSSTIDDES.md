<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des/rtm/kOmegaSSTIDDES -->

# k\-ω\-SST Improved Delayed Detached Eddy Simulation (IDDES)

## Properties

* Two equation model for the turbulence kinetic energy, kkk, and
turbulence specific dissipation rate, ω\\omegaω.
* Based on the [k\-omega SST](../../ras/linear-evm/rtm/kOmegaSST.md) model

## Model equations

The model equations are the same as used by the
[DES variant](kOmegaSSTIDDES.md#model-equations)
of the model, with a different approximation for d\~\\tilde{d}d\~:

## Default model coefficients

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        kOmegaSSTIDDES;
}

```

## Boundary conditions

Inlet

* [fixedValue](../../../../boundary-conditions/rtm/derived/general/fixedValue.md)

Outlet

* [Constrained outlet](../../../../boundary-conditions/rtm/derived/inletOutlet/inletOutlet.md)

Walls

* wall functions

## Further information

Source code:

* [Foam::LESModels::kOmegaSSTIDDES](https://api.openfoam.com/2606/Foam_LESModels_kOmegaSSTIDDES.html)

References:

* *Gritskevich et al.* [22](../../../../../../references.md#gritskevich_development_2012)

See also:

* [DES variant](kOmegaSSTDES.md)
