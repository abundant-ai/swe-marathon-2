<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des/rtm/SpalartAllmarasIDDES -->

# Spalart\-Allmaras Improved Delayed Detached Eddy Simulation (IDDES)

## Properties

* One equation model based on a modified turbulence viscosity,
ν\~\\tilde{\\nu}ν\~

## Model equations

The model equations are the same as used by the
[DES variant](SpalartAllmarasDES.md#model-equations)
of the model, with a different approximation for d\~\\tilde{d}d\~:

d\~\=max⁡(fd\~(1\+fe)LRAS\+(1−fd\~)LLES,SMALL) \\tilde{d} \= \\max \\left( \\tilde{f\_d} (1 \+ f\_e) L\_{RAS} \+ (1 \- \\tilde{f\_d}) L\_{LES}, SMALL \\right)d\~\=max(fd​\~​(1\+fe​)LRAS​\+(1−fd​\~​)LLES​,SMALL)
## Default model coefficients

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        SpalartAllmarasIDDES;
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

* [Foam::LESModels::SpalartAllmarasIDDES](https://api.openfoam.com/2606/Foam_LESModels_SpalartAllmarasIDDES.html)

References:

* *Gritskevich et al.* [22](../../../../../../references.md#gritskevich_development_2012)
