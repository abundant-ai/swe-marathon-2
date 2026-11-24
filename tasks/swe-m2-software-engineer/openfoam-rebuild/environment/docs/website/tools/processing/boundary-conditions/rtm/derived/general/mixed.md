<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/mixed -->

# Mixed

## Properties

* Robin condition
* a linear blend of [fixedValue](fixedGradient.md)
and [gradient](fixedValue.md) conditions
* blending specified using a *value fraction*
* not usually applied directly, but used in derived types, e.g. the
[inletOutlet](../inletOutlet/inletOutlet.md) condition
* explicit and implicit contributions

Face values are evaluated according to:

ϕf\=wϕref\+(1−w)(ϕc\+Δ∇ϕref) \\phi\_f \=
 w \\phi\_{\\ref}
 \+ \\left(1\-w\\right)\\left(\\phi\_c \+ \\Delta \\grad{\\phi}\_{\\ref} \\right)ϕf​\=wϕref​\+(1−w)(ϕc​\+Δ∇ϕref​)
where
ϕf\\phi\_fϕf​
: face value

ϕc\\phi\_cϕc​
: cell value

ϕref\\phi\_{\\ref}ϕref​
: reference value

Δ\\DeltaΔ
: face\-to\-cell distance

www
: value fraction

## Usage

```
<patchName>
{
    type            mixed;
    refValue        <field value>;
    refGradient     <field value>;
    valueFraction   <field value>;
}

```

## Further information

Source code:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)
