<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/rtm/localEuler -->

# Local Euler implicit/explicit time scheme

## Properties

* First order
* Pseudo transient, designed for steady cases
* Spatially varying, cell\-based time scale set by specific Local Time Stepping (LTS) solvers

## Usage

The scheme is specified using:

```
ddtSchemes
{
    default         localEuler;
    ddt(phi)        localEuler;
}

```

## Further information

Source code

* [Foam::fv::localEulerDdtScheme](https://api.openfoam.com/2606/Foam_fv_localEulerDdtScheme.html)
