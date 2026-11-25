<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/externalCoupled -->

# externalCoupled

## Description

The `externalCoupled` function object provides a simple file\-based communication
interface for explicit coupling with an external application, so that data is
transferred to\- and from OpenFOAM. The data exchange employs specialised
boundary conditions to provide either one\-way or two\-way coupling models.

The coupling is through plain text files where OpenFOAM boundary data
is read/written as one line per face (data from all processors collated):

```
# Patch: <patch name>
<fld1> <fld2> .. <fldn>             //face0
<fld1> <fld2> .. <fldn>             //face1
..
<fld1> <fld2> .. <fldn>             //faceN

```

where the actual entries depend on the boundary condition type:

* mixed: value, snGrad, refValue, refGrad, valueFraction
* externalCoupledMixed: output of writeDataMaster
* other: value, snGrad

These text files are located in a user specified communications directory
which gets read/written on the master processor only.

In the communications directory the structure will be:

```
<regionsName>/<patchGroup>/<fieldName>.[in|out]

```

(where `regionsName` is either the name of a single region or a composite
of multiple region names)

At start\-up, the boundary creates a lock file, i.e.:

```
OpenFOAM.lock

```

... to signal the external source to wait. During the function object execution
the boundary values are written to files (one per region, per patch(group),
per field), e.g.:

```
<regionsName>/<patchGroup>/<fieldName>.out

```

The lock file is then removed, instructing the external source to take control
of the program execution. When ready, the external program should create the
return values, e.g. to files:

```
<regionsName>/<patchGroup>/<fieldName>.in

```

... and then reinstate the lock file. The function object will then read these
values, apply them to the boundary conditions and pass program execution back
to OpenFOAM.

## Usage

Example of the `externalCoupled` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
externalCoupled1
{
    // Mandatory entries (unmodifiable)
    type            externalCoupled;
    libs            (fieldFunctionObjects);
    // Directory to use for data exchange
    commsDir        "${FOAM_CASE}/comms";
    regions
    {
        // Region name (wildcards allowed)
        <regionName>
        {
            // Patch or patchGroup
            coupleGroup
            {
                // Fields to output in commsDir
                writeFields (<fields>);

                // Fields to read from commsDir
                readFields  (<fields>);
            }
        }
    }
    initByExternal  true;

    // Optional entries (runtime modifiable)
    waitInterval    1;
    timeOut         100;
    statusDone      done;  // Any arbitrary status=... value
    calcFrequency   1;

    // Optional (inherited) entries

}

```

This reads/writes (on the master processor) the directory:

```
comms/region0_region1/TPatchGroup/

```

with contents:

```
patchPoints     (collected points)
patchFaces      (collected faces)
p.in            (input file of p, written by external application)
T.out           (output file of T, written by OpenFOAM)

```

The `patchPoints/patchFaces` files denote the (collated) geometry
which will be written if it does not exist yet or can be written as
a preprocessing step using the `createExternalCoupledPatchGeometry`
application.

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: externalCoupled | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| commsDir | Communication directory | word | yes | \- |
| regions | The regions to couple | word | yes | \- |
| initByExternal | Initialization values supplied by external app | bool | yes | \- |
| waitInterval | Wait interval in \[s] | label | no | 1 |
| timeOut | Timeout in \[s] | label | no | 100\*waitInterval |
| statusDone | Lockfile status\=... on termination | word | no | done |
| calcFrequency | Calculation frequency | label | no | 1 |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Stored properties

None.

## Further information

Tutorial:

* [externalCoupledSquareBendLiq](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/externalCoupledSquareBendLiq)
* [externalCoupledHeater](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam/externalCoupledHeater)
* [externalCoupledHeater](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionSimpleFoam/externalCoupledHeater)

Source code:

* [externalCoupled](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/externalCoupled)

API:

* [Foam::functionObjects::externalCoupled](https://api.openfoam.com/2606/Foam_functionObjects_externalCoupled.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
