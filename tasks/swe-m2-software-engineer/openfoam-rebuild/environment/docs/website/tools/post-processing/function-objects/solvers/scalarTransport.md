<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/solvers/scalarTransport -->

# Scalar transport

The `scalarTransport` function object evolves a scalar transport equation, which
can be seeded using

* boundary conditions, e.g.
[fixed value](../../../processing/boundary-conditions/rtm/derived/general/fixedValue.md)
* equation sources, e.g. `fvOptions`

## Usage

Basic operation of the `scalarTransport` function object comprises:

```
scalar1
{
    type            scalarTransport;
    libs            ("libsolverFunctionObjects.so");
}

```

For more complete control, the full set of input entries includes:

```
scalar1
{
    type            scalarTransport;
    libs            ("libsolverFunctionObjects.so");

    // Optional entries

    // Name of scalar field to transport, default = 's'
    field           vapour;

    // Name of flux field, default = 'phi'
    phi             phi;

    // Name of density field for compressible cases, default = 'rho'
    rho             rho;

    // Name of phase field to constrain scalar to, default = 'none'
    phase           none;

    // Set the scalar to zero on start/re-start
    resetOnStartUp  no;

    // Name of field to use when looking up schemes from fvSchemes
    // default = <field>
    schemesField    U;

    // Diffusivity

    // Fixed value diffusivity
    D               0.001;

    // Name of field to use as diffusivity, default = 'none'
    nut             none;

    // Run-time selectable sources
    fvOptions
    {
        ...
    }
}

```

Order of importance when setting the *diffusivity*

* Fixed value: `D`
* Field value: `nut`
* If none, the code will
	+ attempt to retrieve the effective viscosity from a turbulence model, or
	+ set a value of zero

## Sample output

The scalar will only be bounded if evolved using the
[upwind](../../../processing/numerics/schemes/divergence/rtm/upwind.md) scheme.

## Further information

Source code:

* [scalarTransport](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/solvers/scalarTransport)

API:

* [Foam::functionObjects::scalarTransport](https://api.openfoam.com/2606/Foam_functionObjects_scalarTransport.html)

Example usage:

* [chtMultiRegionFoam](../../../processing/solvers/rtm/heat-transfer/chtMultiRegionFoam.md)
`windshieldCondensation` tutorial:
[windshieldCondensation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam/windshieldCondensation)
