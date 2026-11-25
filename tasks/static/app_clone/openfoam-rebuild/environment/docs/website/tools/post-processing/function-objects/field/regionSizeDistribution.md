<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/regionSizeDistribution -->

# regionSizeDistribution

## Description

The `regionSizeDistribution` function object
creates a droplet size distribution via interrogating a continuous phase
fraction field.

Looks up a phase\-fraction (alpha) field and splits the mesh into regions
based on where the field is below the threshold value. These
regions ("droplets") can now be analysed.

Regions:

* print the regions connected to a user\-defined set of patches.

```
(in spray calculation these form the liquid core)

```

* print the regions with too large volume. These are the 'background'

```
regions.

```

* (debug) write regions as a `volScalarField`
* (debug) print for all regions the sum of volume and alpha\*volume

Output (volume scalar) fields include:

* alpha\_liquidCore : alpha with outside liquid core set to 0
* alpha\_background : alpha with outside background set to 0\.

Histogram:

* determine histogram of diameter (given `minDiameter`, `maxDiameter`, `nBins`)
* write graph of number of droplets per bin
* write graph of sum, average and deviation of droplet volume per bin
* write graph of sum, average and deviation of user\-defined fields. For

```
`volVectorField`s these are those of the 3 components and the magnitude.

```

* (optional) write graph of histogram of centroids on iso planes

```
downstream of the injector determined by `origin`, `direction` and
`maxDiameter` up to `maxDownstream`

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | `$FOAM_CASE/postProcessing/<FO>/<time>/<files>` |
| output field | \- | \- |

## Usage

Example of the `regionSizeDistribution` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
regionSizeDistribution1
{
    // Mandatory entries (unmodifiable)
    type            regionSizeDistribution;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    field           alpha;
    patches         (inlet);
    fields          (p U);
    threshold       0.4;
    maxDiameter     5e-5;
    nBins           100;
    setFormat       gnuplot;

    // Optional entries (runtime modifiable)
    minDiameter     0.0;
    coordinateSystem
    {
        origin  (0 0 0);
        rotation
        {
            type    axes;
            e3      (0 0 1);
            e1      (1 0 0);
        }
    }

    // Optional downstream iso-plane bins
    isoPlanes       true;

        // Mandatory entries if isoPlanes=true   (runtime modifiable)
        // Plane normal and point definition
        origin          (1e-4 0 5e-4);
        direction       (1 0 1);

        // Maximum diameter of the cylinder formed by the origin point
        // and direction
        maxD            3e-4;

        // Maximum downstream distance
        maxDownstream   6e-4;

        // Number of iso-plane bins
        nDownstreamBins 20;

    // Optional (inherited) entries
    writePrecision  8;
    writeToFile     true;
    useUserTime     true;
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: regionSizeDistribution | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Phase field to interrogate | word | yes | \- |
| patches | Patches wherefrom the liquid core is identified | wordList | yes | \- |
| fields | Fields to sample | wordList | yes | \- |
| threshold | Phase fraction applied to delimit regions | scalar | yes | \- |
| maxDiameter | Maximum droplet diameter | scalar | yes | \- |
| minDiameter | Minimum droplet diameter | scalar | no | 0\.0 |
| nBins | Number of bins for histogram | label | yes | \- |
| setFormat | Output format | word | yes | \- |
| isoPlanes | Flag for isoPlanes | bool | no | false |
| origin | Origin of the plane when isoPlanes is used | vector | yes | \- |
| direction | Direction of the plane when isoPlanes is used | vector | yes | \- |
| maxD | Maximum diameter of the sampling cylinder when isoPlanes is used | vector | yes | \- |
| nDownstreamBins | Number of bins when isoPlanes is used | label | yes | \- |
| maxDownstream | Maximum distance from origin when isoPlanes is used | scalar | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [bubbleColumn](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/twoPhaseEulerFoam/RAS/bubbleColumn)

Source code:

* [regionSizeDistribution](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/regionSizeDistribution)

API:

* [Foam::functionObjects::regionSizeDistribution](https://api.openfoam.com/2606/Foam_functionObjects_regionSizeDistribution.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
