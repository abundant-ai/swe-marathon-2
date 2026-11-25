<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des/rtm/kOmegaSSTDDES -->

# k\-ω\-SST Delayed Detached Eddy Simulation (DDES)

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
    LESModel        kOmegaSSTDDES;
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

* [Foam::LESModels::kOmegaSSTDDES](https://api.openfoam.com/2606/Foam_LESModels_kOmegaSSTDDES.html)

References:

* *Gritskevich et al.* [22](../../../../../../references.md#gritskevich_development_2012)

See also:

* [DES variant](kOmegaSSTDES.md)
