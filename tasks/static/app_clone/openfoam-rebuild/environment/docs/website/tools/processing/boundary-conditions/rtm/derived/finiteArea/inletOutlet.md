<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/inletOutlet -->

# inletOutlet

## Description

The `inletOutlet` is a boundary condition that provides
a generic outflow condition, with specified inflow for the case of return flow.

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
    type            inletOutlet;
    inletValue      <Field>;

    // Optional entries
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `inletOutlet` | word | yes | \- |
| `inletValue` | Inlet value field | scalarField | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* mixedFaPatchField.H

* The mode of operation is determined by the sign of the flux across the
patch edges.
* Sign conventions:
	+ Positive flux (out of domain): apply zero\-gradient condition
	+ Negative flux (into domain): apply the "inletValue" fixed\-value

## Further information

Tutorial:

* [planeTransport](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/finiteArea/surfactantFoam/planeTransport)

Source code:

* [inletOutlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/inletOutlet)

API:

* [Foam::inletOutletFaPatchField](https://api.openfoam.com/2606/Foam_inletOutletFaPatchField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
