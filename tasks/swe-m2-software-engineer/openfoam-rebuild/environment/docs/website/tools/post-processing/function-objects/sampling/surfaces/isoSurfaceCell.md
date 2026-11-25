<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/surfaces/isoSurfaceCell -->

# isoSurfaceCell

Creates iso\-surfaces according to constant field values on a mesh.

## Usage

Basic operation of the `isoSurfaceCell` surface comprises:

```
surfaces1
{
    type            surfaces;
    libs            (sampling);

    surfaces
    {
        mySurface1
        {
            type        isoSurfaceCell;
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
        }
    }
}

```

## Sample output

## Further information

See also

* [isoSurface](isoSurfaceCell.md)

Source code:

* [isoSurfaceCell.H](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/surface/isoSurface/isoSurfaceCell.H)

API

* [Foam::isoSurfaceCell](https://api.openfoam.com/2606/Foam_isoSurfaceCell.html)

Example usage:

* [porousDamBreak](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/multiphase/interIsoFoam/porousDamBreak)
