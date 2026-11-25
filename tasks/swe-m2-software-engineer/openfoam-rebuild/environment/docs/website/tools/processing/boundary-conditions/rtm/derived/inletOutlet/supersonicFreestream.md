<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/supersonicFreestream -->

# supersonicFreestream

## Description

The `supersonicFreestream` is a boundary condition that provides a supersonic
free\-stream condition.

* supersonic inflow is assumed to occur according to the Prandtl\-Meyer
expansion process.
* subsonic outflow is applied via a zero\-gradient condition from inside
the domain.

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
    type            supersonicFreestream;
    UInf            <vector>;
    pInf            <scalar>;
    TInf            <scalar>;
    gamma           <scalar>;

    // Optional entries
    T               <word>;
    p               <word>;
    psi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `supersonicFreestream` | word | yes | \- |
| `UInf` | Freestream velocity | vector | yes | \- |
| `pInf` | Freestream pressure | vector | yes | \- |
| `TInf` | Freestream temperature | vector | yes | \- |
| `gamma` | Heat capacity ratio | scalar | yes | \- |
| `T` | Name of temperature field | word | no | T |
| `p` | Name of pressure field | word | no | p |
| `psi` | Name of compressibility field | word | no | thermo:psi |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

## Further information

Tutorial:

* [nacaAirfoil](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/sonicFoam/RAS/nacaAirfoil)

Source code:

* [supersonicFreestream](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/supersonicFreestream)

API:

* [Foam::supersonicFreestreamFvPatchVectorField](https://api.openfoam.com/2606/Foam_supersonicFreestreamFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
