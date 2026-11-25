<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/lagrangian/cloudInfo -->

# Cloud information

The `cloudInfo` function object generates statistics for a list of clouds,
including:

* number of parcels
* total mass of parcels
* maximum diameter
* Arithmetic mean diameter, D10D\_{10}D10​
* Sauter mean diameter, D32D\_{32}D32​

## Usage

The `cloudInfo` function object is specified using:

```
cloudInfo1
{
    type        cloudInfo;
    libs        ("liblagrangianFunctionObjects.so");

    clouds      (kinematicCloud1  thermoCloud1);
}

```

## Sample output

```
cloudInfo cloudInfo1 write:
    number of parcels : 1234
    mass in system    : 1.234
    maximum diameter  : 1.0
    D10 diameter      : 0.5
    D32 diameter      : 0.6

```

## Further information

Source code:

* [cloudInfo](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/lagrangian/cloudInfo)

API:

* [Foam::functionObjects::cloudInfo](https://api.openfoam.com/2606/Foam_functionObjects_cloudInfo.html)
