<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des/rtm/SpalartAllmarasDES -->

# Spalart\-Allmaras Detached Eddy Simulation (DES)

## Properties

* One equation model based on a modified turbulence viscosity,
ν\~\\tilde{\\nu}ν\~

## Model equations

The ν\~\\tilde{\\nu}ν\~ transport equation is given by:

 \\Ddt{\\rho \\tilde{\\nu}}
 \=
 \\div \\left( \\rho D\_\\tilde{\\nu} \\tilde{\\nu} \\right)
 \+ \\frac{C\_{b2}}{\\sigma\_{\\nu\_t}} \\rho \\mag{\\grad \\tilde{\\nu}}^2
 \+ C\_{b1} \\rho \\tilde{S} \\tilde{\\nu} \\left(1 \- f\_{t2}\\right)
 \- \\left(C\_{w1} f\_w \- \\frac{C\_{b1}}{\\kappa^2} f\_{t2}\\right)
 \\rho \\frac{\\tilde{\\nu}^2}{\\tilde{d}^2}
 \+ S\_\\tilde{\\nu}
where the length scale d\~\\tilde{d}d\~ is defined by:

d\~\=min⁡(ΨCDESΔ,y) \\tilde{d} \= \\min \\left( \\Psi C\_{DES} \\Delta, y \\right)d\~\=min(ΨCDES​Δ,y)
and Ψ\\PsiΨ is the low Reynolds number correction function:

Ψ2\=min⁡\[102,1−1−Cb1Cw1κ2fw∗\[ft2\+(1−ft2)fv2]fv1max⁡(10−10,1−ft2)] \\Psi^2 \=
 \\min
 \\left\[
 10^2,
 \\frac{1 \- \\frac{1 \- C\_{b1}}{C\_{w1} \\kappa^2 f\_w^{\*}} \\left\[ f\_{t2} \+ \\left(1 \- f\_{t2}\\right) f\_{v2} \\right]}{f\_{v1} \\max \\left(10^{\-10}, 1\-f\_{t2} \\right)}
 \\right]Ψ2\=min\[102,fv1​max(10−10,1−ft2​)1−Cw1​κ2fw∗​1−Cb1​​\[ft2​\+(1−ft2​)fv2​]​]
## Default model coefficients

| σνt\\sigma\_{\\nu\_t}σνt​​ | Cb1C\_{b1}Cb1​ | Cb2C\_{b2}Cb2​ | Cw1C\_{w1}Cw1​ | Cw2C\_{w2}Cw2​ | Cw3C\_{w3}Cw3​ |
| --- | --- | --- | --- | --- | --- |
| 2/3 | 0\.1355 | 0\.622 | Cb1κ2\+1\+Cb2σνt\\frac{C\_{b1}}{\\kappa^2} \+ \\frac{1 \+ C\_{b2}}{\\sigma\_{\\nu\_t}} κ2Cb1​​\+σνt​​1\+Cb2​​ | 0\.3 | 2 |

| Cv1C\_{v1}Cv1​ | CsC\_{s}Cs​ | CDESC\_{\\mathit{DES}}CDES​ | CkC\_{k}Ck​ | Ct3C\_{t3}Ct3​ | Ct4C\_{t4}Ct4​ | fw∗f\_w^{\*}fw∗​ |
| --- | --- | --- | --- | --- | --- | --- |

```
7.1 |           0.3 |                      0.65 |    0.07      |   1.2          | 0.5 | 0.424

```

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        SpalartAllmarasDES;

    // Optional entries
    SpalartAllmarasDESCoeffs
    {
        // Apply low-Reynolds number correction; default = yes
        lowReCorrection     yes;
    }
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

* [Foam::LESModels::SpalartAllmarasDES](https://api.openfoam.com/2606/Foam_LESModels_SpalartAllmarasDES.html)

References:

* Principle reference: *Spalart et al.* [67](../../../../../../references.md#spalart_comments_1997)
* Low Reynolds number correction: *Spalart et al.* [68](../../../../../../references.md#spalart_new_2006)
