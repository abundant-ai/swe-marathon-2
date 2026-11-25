<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/laplacian -->

# Laplacian schemes

Taking the Laplacian of a property ϕ\\phiϕ is represented using the notation:

∇2ϕ\=∂2∂x12ϕ\+∂2∂x22ϕ\+∂2∂x32ϕ \\laplacian \\phi
 \=
 \\frac{\\partial^2}{\\partial x\_1^2} \\phi
 \+ \\frac{\\partial^2}{\\partial x\_2^2} \\phi
 \+ \\frac{\\partial^2}{\\partial x\_3^2} \\phi∇2ϕ\=∂x12​∂2​ϕ\+∂x22​∂2​ϕ\+∂x32​∂2​ϕ
or as a combination of divergence and gradient operators

∇ ∙ (Γ∇ϕ) \\div \\left( \\Gamma \\grad \\phi \\right)∇∙(Γ∇ϕ)
where Γ\\GammaΓ is a diffusion coefficient.

## Usage

Laplacian schemes are specified in the
[fvSchemes](../../../../fundamentals/case-structure/fvschemes.md) file under the `laplacianSchemes`
sub\-dictionary using the syntax:

```
laplacianSchemes
{
    default         none;
    laplacian(gamma,phi) Gauss <interpolation scheme> <snGrad scheme>
}

```

All options are based on the application of
[Gauss theorem](gauss-theorem.md), requiring an
[interpolation scheme](interpolation.md) to
transform coefficients from cell values to the faces, and a
[surface\-normal gradient](sngrad/index.md) scheme.

## Example

## Further information

* See the [implementation details](laplacian/implementation-details.md) to see how the
schemes are coded.
