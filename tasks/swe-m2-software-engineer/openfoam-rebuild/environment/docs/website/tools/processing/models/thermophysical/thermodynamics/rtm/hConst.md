<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/rtm/hConst -->

# Constant (enthalpy)

Heat capacity at constant pressure, cpc\_pcp​ \[J/kg/K]

cp\=constantc\_p \= \\text{constant}cp​\=constant
## Usage

The `hConst` thermodynamics model is defined using the entries:

```
thermodynamics
{
    Cp              <scalar>;
    Hf              <scalar>;
    Tref            <scalar>;
    Href            <scalar>;
}

```

Where

* `Cp` : specific heat capacity at constant pressure \[J/kg/K]
* `Hf` : heat of formation \[J/kg]
* `Tref` : reference temperature \[K]; default is `Tstd`
* `Href` : reference sensible enthalpy around which to linearise \[J/kg];
default is zero.

## Further information

Source code

* [hConst](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/thermo/hConst)
