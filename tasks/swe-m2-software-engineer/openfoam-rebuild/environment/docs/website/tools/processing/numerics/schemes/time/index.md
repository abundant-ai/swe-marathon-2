<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/ -->

# Time schemes

Time schemes define how a property is integrated as a function of time, i.e.

∂∂t(ϕ) \\ddt{\\phi}∂t∂​(ϕ)
Depending on the choice of scheme, field values at previous time steps are
required, represented in the following as ϕo\\old{\\phi}ϕo and
ϕoo\\oldold{\\phi}ϕoo for the old and old\-old time levels.

## Usage

Time scheme properties are input in the [fvSchemes](../../../../../fundamentals/case-structure/fvschemes.md)
file under the `ddtSchemes` sub\-dictionary using the syntax:

```
ddtSchemes
{
    default         none;
    ddt(Q)          <time scheme>;
}

```

## Options

Available time schemes include

* [Backward time scheme](rtm/backward.md)
* [Crank\-Nicolson time scheme](rtm/CrankNicolson.md)
* [Euler implicit time scheme](rtm/Euler.md)
* [Local Euler implicit/explicit time scheme](rtm/localEuler.md)
* [Steady state time scheme](rtm/steadyState.md)

## Example

See [this example](example.md) to see the relative performance of the schemes.

## Further information

Source code:

* [ddtScheme](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/finiteVolume/ddtSchemes/ddtScheme)

API:

* [Foam::fv::ddtScheme](https://api.openfoam.com/2606/Foam_fv_ddtScheme.html)
