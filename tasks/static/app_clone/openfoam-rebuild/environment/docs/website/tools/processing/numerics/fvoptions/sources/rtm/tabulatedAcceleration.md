<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/tabulatedAcceleration -->

# Tabulated acceleration

## Properties

## Usage

The option is specified using:

```
disk1
{
    type            tabulatedAccelerationSource;
    selectionMode   cellSet;
    cellSet         sourceCells1;
    fields          (U);

    timeDataFileName "constant/acceleration-terms.dat";
}

```

The `timeDataFileName` provides the name of a file containing a list of
the motion as a function of time, e.g.:

```
//     t      acc    omega   dOmegadt
(
    ( 0.0  ((1 0 0) (0 0 0) (0 0 0)))
    (10.0  ((2 0 0) (0 0 0) (0 0 0)))
);

```

where:

* `t` \= time \[s]
* `acc` \= acceleration vector \[m/s2]
* `omega` \= rotation vector \[rad/s]
* `dOmegadt` \= angular acceleration \[rad/s2]

## Further information

Tutorials

* *none*

Source code

* [tabulatedAccelerationSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/tabulatedAccelerationSource)
