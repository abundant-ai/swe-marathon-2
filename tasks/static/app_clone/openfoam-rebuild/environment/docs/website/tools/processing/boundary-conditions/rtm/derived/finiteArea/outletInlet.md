<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/outletInlet -->

# outletInlet

## Description

The `outletInlet` is a boundary condition that provides
a generic inflow condition, with specified outflow for the case of reverse flow.

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
    type            outletInlet;
    outletValue     <Field>;

    // Optional entries
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `outletInlet` | word | yes | \- |
| `outletValue` | Outlet value field | scalarField | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* mixedFaPatchField.H

* The mode of operation is determined by the sign of the flux across the
patch edges.
* Sign conventions:
	+ Positive flux (out of domain): apply the "outletValue" fixed\-value
	+ Negative flux (into domain): apply zero\-gradient condition

## Further information

Tutorial:

* [planeTransport](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/finiteArea/surfactantFoam/planeTransport)

Source code:

* [outletInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/outletInlet)

API:

* [Foam::outletInletFaPatchField](https://api.openfoam.com/2606/Foam_outletInletFaPatchField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
