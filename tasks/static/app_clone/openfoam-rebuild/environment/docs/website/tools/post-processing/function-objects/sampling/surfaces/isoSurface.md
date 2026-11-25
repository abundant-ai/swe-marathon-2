<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/surfaces/isoSurface -->

# sampledIsoSurface

Creates iso\-surfaces according to constant field values on a mesh.

## Usage

Basic operation of the `isoSurface` surface comprises:

```
surfaces1
{
    type            surfaces;
    libs            (sampling);

    surfaces
    {
        mySurface1
        {
            type            isoSurface;
            isoField        <field-name>;
            isoValues       (<field-values>);

            // Optional entries
            average         false;
            triangulate     false;
            simpleSubMesh   false;

            regularise      ;
            snap            true;
            mergeTol        ;
            bounds          ;

            isoMethod       <isoMethod-type>;
        }
    }
}

```

isoMethod types:

* `default`:
* `cell`:
* `point`:
* `topo`:

filter types:

* `none`:
* `partial`:
* `full`:
* `clean`:
* `cell`:
* `diagCell`

## Sample output

## Further information

Source code:

* [isoSurface](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/sampledSurface/isoSurface)

API:

* [Foam::isoSurface](https://api.openfoam.com/2606/Foam_sampledIsoSurface.html)

Example usage:

* [squareBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/squareBend)
* [propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)
