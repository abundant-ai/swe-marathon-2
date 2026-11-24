<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des/rtm/SpalartAllmarasDDES -->

# Spalart\-Allmaras Delayed Detached Eddy Simulation (DDES)

## Properties

* One equation model based on a modified turbulence viscosity,
ν\~\\tilde{\\nu}ν\~
* based on the [Spalart\-Allmaras DES](SpalartAllmarasDES.md)
model.

## Model equations

The model equations are the same as used by the
[DES variant](SpalartAllmarasDES.md#model-equations)
of the model, with a different approximation for d\~\\tilde{d}d\~:

d\~\=max⁡\[LRAS−fd,max⁡(LRAS−LLES,0)] \\tilde{d}
 \=
 \\max \\left\[ L\_{RAS} \- f\_d, \\max (L\_{RAS} \- L\_{LES}, 0\) \\right]d\~\=max\[LRAS​−fd​,max(LRAS​−LLES​,0)]
The [RAS](../../ras.md) length scale is:

LRAS\=y L\_{RAS} \= yLRAS​\=y
and the [LES](../../les.md) length:

LLES\=ΨCDESΔ L\_{LES} \= \\Psi C\_{DES} \\DeltaLLES​\=ΨCDES​Δ
The delay function is given by:

fd\=1−tanh⁡\[(Cd1rd)Cd2] f\_d \= 1 \- \\tanh \\left\[ \\left( C\_{d1} r\_d \\right)^{C\_{d2}} \\right]fd​\=1−tanh\[(Cd1​rd​)Cd2​]
Here, when fd\=0f\_d \= 0fd​\=0 [RAS](../../ras.md) is recovered, and
when fd\=1f\_d \= 1fd​\=1 the [DES](SpalartAllmarasDES.md)
mode is recovered. The rdr\_drd​ parameter is given by:

rd\=min⁡(νeff∣∇u∣κ2y2,10) r\_d \= \\min \\left( \\frac{\\nu\_{\\mathit{eff}}}{\\mag {\\grad \\u} \\kappa^2 y^2}, 10\\right)rd​\=min(∣∇u∣κ2y2νeff​​,10)
## Default model coefficients

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        SpalartAllmarasDDES;
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

* [Foam::LESModels::SpalartAllmarasDDES](https://api.openfoam.com/2606/Foam_LESModels_SpalartAllmarasDDES.html)

References:

* *Spalart et al.* [68](../../../../../../references.md#spalart_new_2006)
