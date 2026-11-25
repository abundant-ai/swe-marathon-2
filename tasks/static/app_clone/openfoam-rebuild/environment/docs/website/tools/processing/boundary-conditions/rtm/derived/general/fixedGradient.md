<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/fixedGradient -->

# Fixed gradient

## Properties

* Neumann condition
* fixed normal\-gradient
* implicit

Face values are evaluated according to:

ϕf\=ϕc\+Δ∇ϕref \\phi\_f \= \\phi\_c \+ \\Delta \\grad{\\phi}\_{\\ref}ϕf​\=ϕc​\+Δ∇ϕref​
where
ϕf\\phi\_fϕf​
: face value

ϕc\\phi\_cϕc​
: cell value

∇(ϕ)ref\\grad(\\phi)\_{\\ref}∇(ϕ)ref​
: reference gradient

Δ\\DeltaΔ
: face\-to\-cell distance

## Usage

```
<patchName>
{
    type        fixedGradient;
    gradient    <field value>;
}

```

## Further information

Source code:

* [Foam::fixedGradientFvPatchField](https://api.openfoam.com/2606/Foam_fixedGradientFvPatchField.html)
