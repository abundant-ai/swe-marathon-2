<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/kOmegaSSTLM -->

# Langtry\-Menter k\-ω Shear Stress Transport (SST)

## Properties

* Based on the [k\-ω Shear Stress Transport (SST)](kOmegaSST.md) model
* Transition from laminar to turbulence
* Four\-equation model
* Also known as the γ−Reθ\\gamma \- Re\_\\thetaγ−Reθ​ model

## Model equations

## Default model coefficients

## Initialisation

See [kOmegaSST initialisation](kOmegaSST.md#initialisation)

## Boundary conditions

Inlet

* Intermittency:

γ\=1 \\gamma \= 1γ\=1
* Transition momentum thickness Reynolds number:

Reθ\={1173\.51−589\.428Tu\+0\.2196Tu2if Tu≤1\.3331\.5(Tu−0\.5658)0\.671if Tu\>1\.3 Re\_\\theta \=
 \\begin{cases}
 1173\.51 \- 589\.428 Tu \+ \\frac{0\.2196}{Tu^2} \& \\text{if } Tu \\le 1\.3 \\\\
 \\frac{331\.5}{(Tu \- 0\.5658\)^{0\.671}} \& \\text{if } Tu \> 1\.3
 \\end{cases}Reθ​\={1173\.51−589\.428Tu\+Tu20\.2196​(Tu−0\.5658)0\.671331\.5​​if Tu≤1\.3if Tu\>1\.3​
Where:

Tu\=1002/3k∣u∞∣ Tu \= 100 \\frac{\\sqrt{2/3 k}}{\|\\u\_\\infty\|}Tu\=100∣u∞​∣2/3k​​
Walls

* Intermittency: [zero gradient](../../../../../boundary-conditions/rtm/derived/general/zeroGradient.md)

∂∂nγ\=0 \\frac{\\partial}{\\partial n} \\gamma \= 0∂n∂​γ\=0
* Transition momentum thickness Reynolds number: [zero gradient](../../../../../boundary-conditions/rtm/derived/general/zeroGradient.md)

∂∂nReθ\=0 \\frac{\\partial}{\\partial n} Re\_\\theta \= 0∂n∂​Reθ​\=0
## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        kOmegaSSTLM;
}

```

## Further information

Source code:

* [Foam::RASModels::kOmegaSSTLM](https://api.openfoam.com/2606/Foam_RASModels_kOmegaSSTLM.html)

References

* *Langtry and Menter* [35](../../../../../../../references.md#langtry_correlation-based_2009)
* *Menter et al.* [50](../../../../../../../references.md#menter_transition_2006)
* *Langtry* [34](../../../../../../../references.md#langtry_correlation-based_2006)
