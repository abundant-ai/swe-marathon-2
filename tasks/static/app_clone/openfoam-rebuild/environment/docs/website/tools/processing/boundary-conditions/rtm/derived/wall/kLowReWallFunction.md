<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/kLowReWallFunction -->

# kLowReWallFunction

## Description

The `kLowReWallFunction` is boundary condition that provides
a wall function for the turbulent kinetic
energy (i.e. `k`) for low\- and high\-Reynolds number simulations.

Viscous and inertial sublayer predictions for \\c k are blended in
a stepwise manner:

k\=klogify\+\>yintersection\+ k \= k\_{log} \\qquad if \\quad y^\+ \> y^\+\_{intersection}k\=klog​ify\+\>yintersection\+​
k\=kvisify\+\<\=yintersection\+ k \= k\_{vis} \\qquad if \\quad y^\+ \<\= y^\+\_{intersection}k\=kvis​ify\+\<\=yintersection\+​
where:

| Property | Description |
| --- | --- |
| kvisk\_{vis}kvis​ | k prediction in the viscous sublayer |
| klogk\_{log}klog​ | k prediction in the inertial sublayer |
| y\+y^\+y\+ | Estimated wall\-normal height of the cell centre in wall units |
| yintersection\+y^\+\_{intersection}yintersection\+​ | Estimated $$$y^\+$$ where sublayers intersect |

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            kLowReWallFunction;

    // Optional entries
    Ceps2           <scalar>;
    Ck              <scalar>;
    Bk              <scalar>;
    C               <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `kLowReWallFunction` | word | yes | \- |
| `Ceps2` | Model coefficient | scalar | no | 1\.9 |
| `Ck` | Model coefficient | scalar | no | \-0\.416 |
| `Bk` | Model coefficient | scalar | no | 8\.366 |
| `C` | Model coefficient | scalar | no | 11\.0 |

The inherited entries are elaborated in:

* wallFunctionCoefficients.H
* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [kLowReWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/kqRWallFunctions/kLowReWallFunction)

API:

* [Foam::kLowReWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_kLowReWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
