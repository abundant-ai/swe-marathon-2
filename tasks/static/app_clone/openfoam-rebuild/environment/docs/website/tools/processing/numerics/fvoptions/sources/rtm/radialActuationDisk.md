<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/radialActuationDisk -->

# Radial actuation disk

## Properties

* Variant of the [Actuation disk](actuationDisk.md) source that
includes radial thrust

## Usage

The option is specified using:

```
disk1
{
    type            radialActuationDiskSource;
    selectionMode   cellSet;
    cellSet         radialActuationDisk1;
    fields          (U);

    diskDir         (-1 0 0);   // disk direction
    Cp              0.1;        // power coefficient
    Ct              0.5;        // thrust coefficient
    diskArea        5.0;        // disk area
    coeffs          (0.1 0.5 0.01); // radial distribution coefficients
    upstreamPoint   (0 0 0);    // upstream point

```

}

## Further information

Tutorials

* *none*

Source code

* [radialActuationDiskSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/radialActuationDiskSource)

See also

* [Actuation disk](actuationDisk.md)
