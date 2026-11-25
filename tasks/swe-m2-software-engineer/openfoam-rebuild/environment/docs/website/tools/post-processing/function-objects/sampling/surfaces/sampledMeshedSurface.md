<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/surfaces/sampledMeshedSurface -->

# sampledMeshedSurface

Creates a cutting plane through a mesh.

## Usage

Basic operation of the `sampledMeshedSurface` surface comprises:

```
surfaces1
{
    type            surfaces;
    libs            (sampling);

    surfaces
    {
        mySurface1
        {
            type            sampledMeshedSurface;
            source          <source-type>;
            surface         <mySurface-file>;

            // Optional entries

            defaultValue
            {
                <field1-name>       <field1-value>;
                ...
                <field2-name>       <fieldN-value>;
                <fieldN-name>       <fieldN-value>;
            }

            keepIds         <bool>;

            maxDistance     <scalar>;

            patches         (<patch-names>);
        }
    }
}

```

Source types

* `cells`
* `insideCells`
* `boundaryCells`

## Sample output

## Further information

Source code:

* [sampledMeshedSurface](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/sampledSurface/sampledMeshedSurface)

API:

* [Foam::sampledMeshedSurface](https://api.openfoam.com/2606/Foam_sampledMeshedSurface.html)

Example usage:

* [squareBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/squareBend)
* [propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
