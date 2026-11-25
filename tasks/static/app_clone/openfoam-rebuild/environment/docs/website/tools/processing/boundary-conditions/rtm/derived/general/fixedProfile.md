<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/fixedProfile -->

# fixedProfile

## Description

The `fixedProfile` is a generic boundary condition that provides a fixed
value profile condition.

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
    type            fixedProfile;
    profile         <Function1<Type>>;
    dir             <vector>;
    origin          <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedProfile` | word | yes | \- |
| `profile` | Profile data | Function1\<Type\> | yes | \- |
| `dir` | Profile direction | vector | yes | \- |
| `origin` | Profile origin | scalar | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* N/A

Source code:

* [fixedProfile](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedProfile)

API:

* [Foam::fixedProfileFvPatchField](https://api.openfoam.com/2606/Foam_fixedProfileFvPatchField.html)

**History:** Introduced in version [v3\.0\+](https://www.openfoam.com/news/main-news/openfoam-v3.0+)
