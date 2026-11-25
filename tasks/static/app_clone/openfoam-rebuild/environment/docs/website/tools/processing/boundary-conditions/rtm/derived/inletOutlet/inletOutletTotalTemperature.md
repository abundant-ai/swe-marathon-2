<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/inletOutletTotalTemperature -->

# inletOutletTotalTemperature

## Description

The `inletOutletTotalTemperature` is a temperature boundary condition that provides
an outflow condition for total temperature for use with supersonic cases, where
a user\-specified value is applied in the case of reverse flow.

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
    type            inletOutletTotalTemperature;
    T0              <scalarField>;
    gamma           <scalar>;

    // Optional entries
    U               <word>;
    psi             <word>;
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `inletOutletTotalTemperature` | word | yes | \- |
| `T0` | Total temperature patch field | scalarField | yes | \- |
| `gamma` | Heat\-capacity ratio | scalar | yes | \- |
| `U` | Name of velocity field | word | no | U |
| `psi` | Name of compressibility field | word | no | psi |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::inletOutletFvPatchField](https://api.openfoam.com/2606/Foam_inletOutletFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [inletOutletTotalTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/inletOutletTotalTemperature)

API:

* [Foam::inletOutletTotalTemperatureFvPatchScalarField](https://api.openfoam.com/2606/Foam_inletOutletTotalTemperatureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
