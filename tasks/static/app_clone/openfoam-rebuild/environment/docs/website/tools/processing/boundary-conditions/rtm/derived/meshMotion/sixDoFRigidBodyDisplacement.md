<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/sixDoFRigidBodyDisplacement -->

# sixDoFRigidBodyDisplacement

## Description

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
    type            sixDoFRigidBodyDisplacement;

    // Optional entries
    rho             <word>;
    g               <vector>;
    initialPoints   <pointField>;

    // Conditional entries

        // if 'rho rhoInf;'
        rhoInf      <scalar>;

    // Inherited entries
    // sixDoFRigidBodyMotion settings
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `sixDoFRigidBodyDisplacement` | word | yes | \- |
| `rho` | Name of density field | word | no | rho |
| `g` | Gravitational acceleration | vector | no | \- |
| `initialPoints` | Initial positions of points on the patch | pointField | no | \- |
| `rhoInf` | Value of density | scalar | conditional | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H
* sixDoFRigidBodyMotion.H

## Further information

Tutorial:

* [sphereDrop](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/compressibleInterDyMFoam/laminar/sphereDrop)

Source code:

* [sixDoFRigidBodyDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sixDoFRigidBodyMotion/pointPatchFields/derived/sixDoFRigidBodyDisplacement)

API:

* [Foam::sixDoFRigidBodyDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_sixDoFRigidBodyDisplacementPointPatchVectorField.html)

**History:** Introduced in version [2\.3\.0](https://www.openfoam.com/news/main-news/openfoam-2.3.0)
