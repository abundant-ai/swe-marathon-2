<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/outletMappedUniformInlet -->

# outletMappedUniformInlet

## Description

The `outletMappedUniformInlet` is a generic fixed\-value inlet condition that

* averages patch fields of specified "outlet" patches and uniformly applies
the averaged value over a specified inlet patch.
	+ optionally, the averaged value can be scaled and/or offset by a specified value,

```
and/or mapped by a specified time delay.

```

The governing equation of the boundary condition is:

ϕinlet\=∑i(fiϕoutleti\+ϕoffseti) \\phi\_{inlet} \=
 \\sum\_i \\left( f\_i \\phi\_{{outlet}\_i} \+ \\phi\_{{offset}\_i} \\right)ϕinlet​\=i∑​(fi​ϕoutleti​​\+ϕoffseti​​)
where:

| Property | Type |
| --- | --- |
| ϕinlet\\phi\_{inlet}ϕinlet​ | Spatially\-uniform patch\-field value at an inlet patch |
| ϕoutlet\\phi\_{outlet}ϕoutlet​ | Averaged patch\-field value at an outlet patch |
| fff | User\-defined fraction value |
| ϕoffset\\phi\_{offset}ϕoffset​ | User\-defined offset value |
| iii | Outlet\-patch index |

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
    type            outletMappedUniformInlet;

    outlets
    {
        <outletName.1>
        {
            fraction    <Function1<scalar>>;
            offset      <Function1<Type>>;
            timeDelay   <Function1<scalar>>;
        }
        <outletName.2>
        {
            fraction    <Function1<scalar>>;
            offset      <Function1<Type>>;
            timeDelay   <Function1<scalar>>;
        }
        ...
    }

    // Optional entries
    uniformValue    <PatchFunction1<Type>>;
    phi             phi;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `outletMappedUniformInlet` | word | yes | \- |
| `outlets` | Dictionary name: outlets | dict | yes | \- |
| `fraction` | Fraction value | Function1\<scalar\> | no | 1 |
| `offset` | Offset value | Function1\<Type\> | no | Zero |
| `timeDelay` | Time delay | Function1\<scalar\> | no | 0 |
| `uniformValue` | Base inlet patch field | PatchFunction1\<Type\> | no | Zero |
| `phi` | Name of operand flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::PatchFunction1](https://api.openfoam.com/2606/Foam_PatchFunction1.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* Any negative input of `timeDelay` entry is forced to be
zero without emitting any warnings.

## Further information

Tutorial:

* [airRecirculationRoom](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/airRecirculationRoom)

Source code:

* [outletMappedUniformInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/outletMappedUniformInlet)

API:

* [Foam::outletMappedUniformInletFvPatchField](https://api.openfoam.com/2606/Foam_outletMappedUniformInletFvPatchField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
