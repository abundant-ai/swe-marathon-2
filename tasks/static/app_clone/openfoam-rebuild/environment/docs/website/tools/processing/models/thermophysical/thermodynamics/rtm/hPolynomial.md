<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/rtm/hPolynomial -->

# Polynomial (enthalpy)

Heat capacity at constant pressure, cpc\_pcp​ \[J/kg/K]

cp\=∑i\=1NciTi−1c\_p \= \\sum\_{i\=1}^N c\_i T^{i\-1}cp​\=i\=1∑N​ci​Ti−1
## Usage

The `hPolynomial` thermodynamics model is defined using the entries:

```
thermodynamics
{
    Hf              <scalar>;
    Sf              <scalar>;
    CpCoeffs<8>     (<c1> <c2> <c3> <c4> <c5> <c6> <c7> <c8>);
}

```

Where

* `Hf` : heat of formation \[J/kg]
* `Sf` : entropy of formation \[J/kg]
* `CpCoeffs<8>` : Polynomial coefficients (x8\)
* `Tref` : reference temperature \[K]; default is TstdT\_{\\std}Tstd​
* `Href` : reference enthalpy \[J/kg]; default is zero
* `Sref` : reference entropy \[J/kg/K]; default is zero
* `Pref` : reference pressure \[Pa]; default is PstdP\_{\\std}Pstd​

## Further information

Source code

* [hPolynomial](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/thermo/hPolynomial)
