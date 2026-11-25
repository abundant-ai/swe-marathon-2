<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/rtm/janaf -->

# JANAF

The `janaf` model provides thermodynamic property characteristics as a
function of temperature. The model is based on two sets of coefficients that
describe the property variation with temperature above, and below, the model
'common' temperature, TcommonT\_{\\text{common}}Tcommon​, i.e.

coeffs\={lowif T\>Tcommonhighotherwise \\mathrm{coeffs} \=
 \\begin{cases}
 \\mathrm{low} \& \\text{if}\\, T \\gt T\_{\\text{common}} \\\\
 \\mathrm{high} \& \\text{otherwise} \\\\
 \\end{cases}coeffs\={lowhigh​ifT\>Tcommon​otherwise​
The functions are valid within the range 200\<T\<6000  \[K].200 \\lt T \\lt 6000 \\; \\text{\[K]}.200\<T\<6000\[K].

If the bounds are exceeded, calculations will fail with a fatal error.

Heat capacity at constant pressure, cpc\_pcp​ \[J/kg/K]

cp\=c1\+c2T\+c3T2\+c4T3\+c5T5\+cp,eosc\_p \= c\_1 \+ c\_2 T \+ c\_3 T^2 \+ c\_4 T^3 \+ c\_5 T^5 \+ c\_{p, eos}cp​\=c1​\+c2​T\+c3​T2\+c4​T3\+c5​T5\+cp,eos​
Absolute enthalpy, HaH\_aHa​ \[J/kg]

Ha\=c1T\+c2T22\+c3T33\+c4T44\+c5T55\+HeosH\_a \= c\_1 T
 \+ \\frac{c\_2 T^2}{2}
 \+ \\frac{c\_3 T^3}{3}
 \+ \\frac{c\_4 T^4}{4}
 \+ \\frac{c\_5 T^5}{5}
 \+ H\_{eos}Ha​\=c1​T\+2c2​T2​\+3c3​T3​\+4c4​T4​\+5c5​T5​\+Heos​
Entropy, SSS \[J/kg/K]

S\=c1ln⁡T\+c2T\+c3T22\+c4T33\+c5T44\+c6\+SeosS \= c\_1 \\ln T
 \+ c\_2 T
 \+ c\_3 \\frac{T^2}{2}
 \+ c\_4 \\frac{T^3}{3}
 \+ c\_5 \\frac{T^4}{4}
 \+ c\_6
 \+ S\_{eos}S\=c1​lnT\+c2​T\+c3​2T2​\+c4​3T3​\+c5​4T4​\+c6​\+Seos​
## Usage

The `janaf` thermodynamics model is defined using the entries:

```
thermodynamics
{
    Tlow            <scalar>;
    Thigh           <scalar>;
    Tcommon         <scalar>;
    lowCpCoeffs     (<scalar> <scalar> <scalar> <scalar> <scalar> <scalar> <scalar>);
    highCpCoeffs    (<scalar> <scalar> <scalar> <scalar> <scalar> <scalar> <scalar>);
}

```

Where

* `Tlow` : Low temperature limit \[K]
* `Thigh` : High temperature limit \[K]
* `Tcommon` : Common temperature \[K]
* `lowCpCoeffs` : Low coefficients \[]
* `highCpCoeffs` : High coefficients \[]

## Further information

Source code

* [janaf](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/thermo/janaf)
