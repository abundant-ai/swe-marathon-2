<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/outletInlet -->

# outletInlet

## Description

The `outletInlet` is a generic [mixed](../general/mixed.md)
boundary condition that sets the patch value to a user\-specified [fixedValue](../general/fixedGradient.md) for reverse flows, and treats inflow using
a [zeroGradient](../general/zeroGradient.md) condition.

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
    phi             phi;

    // Inherited entries
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `outletInlet` | word | yes | \- |
| `outletValue` | Outlet field for reverse flow | Field | yes | \- |
| `phi` | Name of the local mass flux | word | no | phi |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

* The mode of operation is determined by the sign of the flux across the
patch faces.
* Sign conventions:
	+ Positive flux (out of domain): apply the "outletValue" fixed\-value
	+ Negative flux (into domain): apply zero\-gradient condition

## Further information

Tutorial:

* [drag](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/adjointOptimisationFoam/sensitivityMaps/naca0012/laminar/drag)

Source code:

* [outletInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/outletInlet)

API:

* [Foam::outletInletFvPatchField](https://api.openfoam.com/2606/Foam_outletInletFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
