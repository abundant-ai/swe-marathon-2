<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/turbulentDFSEMInlet/ -->

# turbulentDFSEMInlet

## Description

The `turbulentDFSEMInlet` is a synthesised\-eddy based velocity inlet
boundary condition to generate synthetic turbulence\-alike time\-series
from a given set of turbulence statistics for [LES](../../../../../models/turbulence/les.md)
and [DES](../../../../../models/turbulence/des.md) computations.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            turbulentDFSEMInlet;
    delta           <scalar>;
    R               <PatchFunction1>;
    U               <PatchFunction1>;
    L               <PatchFunction1>;

        // e.g.
        // R        uniform (<Rxx> <Rxy> <Rxz> <Ryy> <Ryz> <Rzz>);
        // U        uniform (<Ux> <Uy> <Uz>);
        // L        uniform <L>;

    // Optional entries
    d               <scalar>;
    nCellPerEddy    <label>;
    kappa           <scalar>;
    Uref            <scalar>;
    Lref            <scalar>;
    scale           <scalar>;
    m               <scalar>;
    writeEddies     <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentDFSEMInlet` | word | yes | \- |
| `delta` | Characteristic length scale | scalar | yes | \- |
| `R` | Reynolds\-stress tensor field | PatchFunction1\<symmTensor\> | yes | \- |
| `U` | Mean velocity field | PatchFunction1\<vector\> | yes | \- |
| `L` | Integral\-length scale field | PatchFunction1\<scalar\> | yes | \- |
| `d` | Ratio of sum of eddy volumes to eddy box volume i.e. eddy density (fill fraction) | scalar | no | 1\.0 |
| `nCellPerEddy` | Minimum eddy length in units of number of cells | label | no | 5 |
| `kappa` | von Karman constant | scalar | no | 0\.41 |
| `Uref` | Normalisation factor for Reynolds\-stress tensor and mean velocity | scalar | no | 1\.0 |
| `Lref` | Normalisation factor for integral\-length scale | scalar | no | 1\.0 |
| `scale` | Heuristic scaling factor being applied on the normalisation factor C1 | scalar | no | 1\.0 |
| `m` | The power of V defined in C1 | scalar | no | 0\.5 |
| `writeEddies` | Flag to write eddies as OBJ file | bool | no | false |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::PatchFunction1](https://api.openfoam.com/2606/Foam_PatchFunction1.html)
* [Foam::PatchFunction1Types::MappedFile](https://api.openfoam.com/2606/Foam_PatchFunction1Types_MappedFile.html)

* The `delta` value typically represents the characteristic scale of flow
or flow domain, e.g. a channel half height for plane channel flows.
* `nCellPerEddy` and `scale` entries are heuristic entries
which do not exist in the standard method, yet are necessary
to reproduce the results published in the original journal paper.
* In the original journal paper, `C1` in Eq. 11 is not dimensionless.
It is not clear whether this dimensionality issue was intentional.
To alleviate this matter, users can alter the input entry `m`, which is
the power of the eddy\-box volume defined in the `C1`, to obtain a
dimensionless `C1` coefficient. The default value of `m` is 0\.5,
which is the value stated in the original journal paper,
and `m=1/3` leads to a dimensionless `C1`.

## Further information

Tutorial:

* [planeChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/planeChannel)

Source code:

* [turbulentDFSEMInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/turbulentDFSEMInlet)

API:

* [Foam::turbulentDFSEMInletFvPatchVectorField](https://api.openfoam.com/2606/Foam_turbulentDFSEMInletFvPatchVectorField.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
