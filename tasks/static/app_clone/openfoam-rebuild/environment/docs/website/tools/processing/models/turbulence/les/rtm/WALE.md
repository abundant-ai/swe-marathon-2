<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/rtm/WALE -->

# Wall Adapting Local Eddy\-viscosity (WALE)

## Properties

* \<B\>W\</B\>all \<B\>A\</B\>dapting \<B\>L\</B\>ocal \<B\>E\</B\>ddy\-viscosity

## Model equations

## Default model coefficients

| CeC\_eCe​ | CkC\_kCk​ | CwC\_wCw​ |
| --- | --- | --- |

```
1.048 |       0.094 |      0.325

```

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        WALE;
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

* [Foam::LESModels::WALE](https://api.openfoam.com/2606/Foam_LESModels_WALE.html)

References:

* *Nicoud and Ducros* [55](../../../../../../references.md#nicoud_subgrid-scale_1999)
