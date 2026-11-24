<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/rtm/hPower -->

# Power (enthalpy)

Heat capacity at constant pressure, cpc\_pcp​ \[J/kg/K]

cp\=c0(TTref)n0\+cp,eosc\_p \= c\_0 \\left( \\frac{T}{T\_{\\ref}} \\right)^{n\_0} \+ c\_{p, eos}cp​\=c0​(Tref​T​)n0​\+cp,eos​
## Usage

The `hPower` thermodynamics model is defined using the entries:

```
thermodynamics
{
    C0              <scalar>;
    n0              <scalar>;
    Tref            <scalar>;
    Hf              <scalar>;
}

```

Where

* `C0` : reference heat capacity at constant pressure \[J/kg/K]
* `n0` : model exponent \[\-];
* `Tref` : reference temperature \[K]
* `Hf` : heat of formation \[J/kg]

## Further information

Source code

* [hPower](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/thermo/hPower)
