<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/inletOutlet -->

# inletOutlet

## Description

The `inletOutlet` is a generic boundary condition that provides an outflow
condition, with specified inflow for the case of return flow.

## Usage

The condition requires entries in both theboundary\` and field files.

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
    type            inletOutlet;
    inletValue      <Field<Type>>;

    // Optional entries
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `inletOutlet` | word | yes | \- |
| `inletValue` | Patch field for reverse flow | Field\<Type\> | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

* The mode of operation is determined by the sign of the flux across the
patch faces.
* Sign conventions:
	+ Positive flux (out of domain): apply zero\-gradient condition.
	+ Negative flux (into domain): apply the `inletValue` fixed\-value.

## Further information

Tutorial:

* [pitzDaily](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/LES/pitzDaily)

Source code:

* [inletOutlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/inletOutlet)

API:

* [Foam::inletOutletFvPatchField](https://api.openfoam.com/2606/Foam_inletOutletFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
