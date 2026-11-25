<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/uncoupledSixDoFRigidBodyDisplacement -->

# uncoupledSixDoFRigidBodyDisplacement

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
    type            uncoupledSixDoFRigidBodyDisplacement;

    // Optional entries
    initialPoints   <pointField>;

    // Inherited entries
    // sixDoFRigidBodyMotion settings
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uncoupledSixDoFRigidBodyDisplacement` | word | yes | \- |
| `initialPoints` | Initial positions of points on the patch | pointField | no | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H
* sixDoFRigidBodyMotion.H

## Further information

Tutorial:

* N/A

Source code:

* [uncoupledSixDoFRigidBodyDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sixDoFRigidBodyMotion/pointPatchFields/derived/uncoupledSixDoFRigidBodyDisplacement)

API:

* [Foam::uncoupledSixDoFRigidBodyDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_uncoupledSixDoFRigidBodyDisplacementPointPatchVectorField.html)

**History:** Introduced in version [2\.3\.0](https://www.openfoam.com/news/main-news/openfoam-2.3.0)
