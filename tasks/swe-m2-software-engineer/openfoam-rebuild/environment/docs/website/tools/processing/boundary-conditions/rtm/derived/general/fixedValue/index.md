<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/fixedValue/ -->

# fixedValue

## Properties

* Dirichlet
* explicit

Face values are evaluated according to:

ϕf\=ϕref \\phi\_f \= \\phi\_{\\ref}ϕf​\=ϕref​
where
ϕf\\phi\_fϕf​
: face value

ϕref\\phi\_{\\ref}ϕref​
: reference value

## Usage

```
<patchName>
{
    type        fixedValue;
    value       <field value>;
}

```

## Further information

Source code:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
