<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/SpalartAllmaras/ -->

# Spalart\-Allmaras

## Properties

* One equation model based on a modified turbulence viscosity,
ν\~\\tilde{\\nu}ν\~

## Model equations

 \\Ddt{\\rho \\tilde{\\nu}}
 \=
 \\div \\left( \\rho D\_\\tilde{\\nu} \\tilde{\\nu} \\right)
 \+ \\frac{C\_{b2}}{\\sigma\_{\\nu\_t}} \\rho \\mag{\\grad \\tilde{\\nu}}^2
 \+ C\_{b1} \\rho \\tilde{S} \\tilde{\\nu} \\left(1 \- f\_{t2}\\right)
 \- \\left(C\_{w1} f\_w \- \\frac{C\_{b1}}{\\kappa^2} f\_{t2}\\right)
 \\rho \\frac{\\tilde{\\nu}^2}{\\tilde{d}^2}
 \+ S\_\\tilde{\\nu}
The ft2f\_{t2}ft2​ term is not implemented.

The turbulence viscosity is obtained using:

νt\=ν\~fv1 \\nu\_t \= \\tilde{\\nu} f\_{v1}νt​\=ν\~fv1​
where the function fv1f\_{v1}fv1​ is given by

fv1\=χ3χ3\+Cv13 f\_{v1} \= \\frac{\\chi^3}{\\chi^3 \+ C\_{v1}^3}fv1​\=χ3\+Cv13​χ3​
and

χ\=ν\~ν \\chi \= \\frac{\\tilde{\\nu}}{\\nu}χ\=νν\~​
## Default model coefficients

| σνt\\sigma\_{\\nu\_t}σνt​​ | Cb1C\_{b1}Cb1​ | Cb2C\_{b2}Cb2​ | Cw1C\_{w1}Cw1​ | Cw2C\_{w2}Cw2​ | Cw3C\_{w3}Cw3​ |
| --- | --- | --- | --- | --- | --- |
| 2/3 | 0\.1355 | 0\.622 | Cb1κ2\+1\+Cb2σνt\\frac{C\_{b1}}{\\kappa^2} \+ \\frac{1 \+ C\_{b2}}{\\sigma\_{\\nu\_t}} κ2Cb1​​\+σνt​​1\+Cb2​​ | 0\.3 | 2 |

| Cv1C\_{v1}Cv1​ | CsC\_{s}Cs​ |
| --- | --- |
| 7\.1 | 0\.3 |

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        SpalartAllmaras;
}

```

## Further information

Source code:

* [Foam::RASModels::SpalartAllmaras](https://api.openfoam.com/2606/Foam_RASModels_SpalartAllmaras.html)

References:

* Standard model: *Spalart* [69](../../../../../../../../references.md#spalart_one-equation_1994)

Related:

* [Detached Eddy Simulation (DES)](../../../../des.md) variants, e.g.
* [Spalart\-Allmaras Detached Eddy Simulation (DES)](../../../../des/rtm/SpalartAllmarasDES.md)
