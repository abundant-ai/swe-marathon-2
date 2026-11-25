<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/rtm/hTabulated -->

# Tabulated (enthalpy)

Heat capacity at constant pressure, cpc\_pcp​ \[J/kg/K]

cp\=f(p,T)c\_p \= f(p, T)cp​\=f(p,T)
## Usage

The `hTabulated` thermodynamics model is defined using the entries:

```
thermodynamics
{
    Hf              <scalar>;
    Sf              <scalar>;
    Cp
    (
        (<T1>   <cp1>)
        (<T2>   <cp2>)
        (<T3>   <cp3>)
        ...
        (<Tn>   <cpn>)
    )
}

```

Where

* `Hf` : heat of formation \[J/kg]
* `Sf` : entropy of formation \[J/kg]
* `Cp` : List of tuples of (temperature heat capacity) describing the table

## Further information

Source code

* [hTabulated](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/thermo/hTabulated)
