<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/nvd-tvd -->

# NVD and TVD schemes

Many of the convection schemes in OpenFOAM are based on the Normalised
Variable (NV) [40](../../../../../references.md#leonard_simple_1988) and Total Variation Diminishing (TVD)
[23](../../../../../references.md#harten_high_1983) methods. These provide a set tools to characterise
scheme properties such as boundedness (1\-D).

![NVD](/img/tools/processing/numerics/schemes/divergence/nvd.png)![TVD](/img/tools/processing/numerics/schemes/divergence/tvd.png)
## Properties

* Offer a blend between a low order scheme and a higher order scheme based on
the calculation of a limiter
* Boundedness of NVD/TVD schemes is only guaranteed for 1\-D cases
* Boundedness can be improved in 2\-D and 3\-D cases by limiting the
[gradient](../gradient/index.md)

## Limiter calculation

For arbitrary unstructured meshes it is not straightforward to identify the
upstream and downstream locations reliably. The limiters are evaluated using a
compact stencil as described in Jasak et al. [26](../../../../../references.md#jasak_high_1999), where:

TVD: Limiter Ψ(r)\\Psi(r)Ψ(r) defined as a function of rrr

r\=2d ∙ (∇ϕ)Pd ∙ (∇ϕ)f−1\=2d ∙ (∇ϕ)PϕN−ϕP−1 r \= 2 \\frac{\\vec{d} \\dprod \\left( \\grad{\\phi} \\right)\_P}{\\vec{d} \\dprod \\left(\\grad{\\phi} \\right)\_f} \- 1
 \= 2 \\frac{\\vec{d} \\dprod \\left( \\grad{\\phi} \\right)\_P}{\\phi\_N \- \\phi\_P} \- 1r\=2d∙(∇ϕ)f​d∙(∇ϕ)P​​−1\=2ϕN​−ϕP​d∙(∇ϕ)P​​−1
NVD: Limiter ϕf\~\\widetilde{\\phi\_f}ϕf​​ defined as a function of ϕc\~\\widetilde{\\phi\_c}ϕc​​

ϕc\~\=1−0\.5d ∙ (∇ϕ)fd ∙ (∇ϕ)P\=1−0\.5ϕN−ϕPd ∙ (∇ϕ)P \\widetilde{\\phi\_c} \= 1 \- 0\.5 \\frac{\\vec{d} \\dprod \\left( \\grad{\\phi} \\right)\_f}{\\vec{d} \\dprod \\left( \\grad{\\phi}\\right)\_P }
 \= 1 \- 0\.5 \\frac{\\phi\_N \- \\phi\_P}{\\vec{d} \\dprod \\left(\\grad{\\phi}\\right)\_P}ϕc​​\=1−0\.5d∙(∇ϕ)P​d∙(∇ϕ)f​​\=1−0\.5d∙(∇ϕ)P​ϕN​−ϕP​​
Where the gradient at cell P (∇ϕ)P\\left( \\grad{\\phi} \\right)\_P(∇ϕ)P​ is calculated
using the user\-selected gradient scheme, and the vector d\\vec{d}d

d\=CN−CP \\vec{d} \= \\vec{C}\_{N} \- \\vec{C}\_{P}d\=CN​−CP​
## Further information

Source code:

* [NVDTVD.H](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/interpolation/surfaceInterpolation/limitedSchemes/LimitedScheme/NVDTVD.H)
* [LimitedScheme](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/interpolation/surfaceInterpolation/limitedSchemes/LimitedScheme)

API:

* [Foam::NVDTVD](https://api.openfoam.com/2606/Foam_NVDTVD.html)
* [Foam::LimitedScheme](https://api.openfoam.com/2606/Foam_LimitedScheme.html)
