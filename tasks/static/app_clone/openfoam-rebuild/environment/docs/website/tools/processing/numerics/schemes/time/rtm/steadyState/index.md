<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/rtm/steadyState/ -->

# Steady state time scheme

## Properties

* Steady state
* Sets temporal derivative contributions to zero

∂∂t(ϕ)\=0 \\ddt{\\phi} \= 0∂t∂​(ϕ)\=0
## Usage

The scheme is specified using:

```
ddtSchemes
{
    default         steadyState;
}

```

## Further information

Source code

* [Foam::fv::steadyStateDdtScheme](https://api.openfoam.com/2606/Foam_fv_steadyStateDdtScheme.html)

Additional

* (scheme settings)\[../../divergence\#special\-cases\-steady\-state)
