<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/rtm/eConst -->

# Constant (energy)

Heat capacity at constant volume, cvc\_vcv​ \[J/kg/K]

cv\=∑i\=1NciTi−1c\_v \= \\sum\_{i\=1}^N c\_i T^{i\-1}cv​\=i\=1∑N​ci​Ti−1
## Usage

The `eConst` thermodynamics model is defined using the entries:

```
thermodynamics
{
    Cv              <scalar>;
    Hf              <scalar>;
    Tref            <scalar>;
    Esref           <scalar>;
}

```

Where

* `Cv` : specific heat capacity at constant volume \[J/kg/K]
* `Hf` : heat of formation \[J/kg]
* `Tref` : reference temperature \[K]; default is `Tstd`
* `Esref` : reference sensible enthalpy around which to linearise \[J/kg];
default is zero.

## Further information

Source code

* [eConst](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/thermo/eConst)
