<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/turbulentDigitalFilterInlet -->

# turbulentDigitalFilterInlet

## Description

The `turbulentDigitalFilterInlet` is a digital\-filter based boundary condition
for vector\- and scalar\-based quantities (e.g. `U` or `T`) to generate synthetic
turbulence\-alike time\-series from input turbulence statistics for
[LES](../../../../models/turbulence/les.md) and [DES](../../../../models/turbulence/des.md) turbulent
flow computations.

In DFM or FSM, a random number set (mostly white noise), and a group
of target statistics (mostly mean flow, Reynolds\-stress tensor profiles and
integral\-scale sets) are merged into a new number set (stochastic
time\-series, yet consisting of the statistics) by a chain of mathematical
operations whose characteristics are designated by the target statistics,
so that the realised statistics of the new sets could match the target.

```
Random number sets ---->-|
                          |
                      DFM or FSM ---> New stochastic time-series consisting
                          |           turbulence statistics
Turbulence statistics ->-|

```

The main difference between DFM and FSM is that FSM replaces
the expensive\-to\-run streamwise convolution summation in DFM by a simpler
and an almost\-equivalent\-in\-effect numerical procedure in order to reduce
computational costs. Accordingly, FSM potentially brings computational
resource advantages for computations involving relatively large streamwise
integral\-scale sets and small time\-steps.

Synthetic turbulence is generated on a virtual rectangular structured\-mesh
plane and is mapped onto this patch by the selected mapping method.

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
    type            turbulentDigitalFilterInlet;
    n               (<label> <label>);
    mean            <PatchFunction1<vector>> or <PatchFunction1<scalar>>;
    R               <PatchFunction1<symmTensor>> or <PatchFunction1<scalar>>;
    L               <tensor> or <vector>;

    // Optional entries
    kernelType      <word>;
    AMIMethod       <word>;
    coordinateSystem  <coordinateSystem>;
    fsm             <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentDigitalFilterInlet` | word | yes | \- |
| `n` | Number of cells on turbulence generation plane (width height) or (e2 e3\) | Vector2D\<label\> | yes | \- |
| `mean` | Mean quantity | PatchFunction1\<vector\> or PatchFunction1\<scalar\> | yes | \- |
| `R` | Reynolds stresses | PatchFunction1\<symmTensor\> or PatchFunction1\<scalar\> | yes | \- |
| `L` | Integral scales | tensor or vector | yes | \- |
| `kernelType` | Autocorrelation function form | word | no | Gaussian |
| `AMIMethod` | Mapping method | word | no | faceAreaWeightAMI |
| `coordinateSystem` | Coordinate system of turbulence generation plane | coordinateSystem | no | \- |
| `fsm` | Flag to turn on the forward\-stepwise method | bool | no | false |

The inherited entries are elaborated in:

* [fixedValueFvPatchField.H](../general/fixedValue.md)
* PatchFunction1\.H
* AMIPatchToPatchInterpolation.H
* coordinateSystem.H
* IntegralScaleBox.H

Options for the `kernelType` entry:

| Property | Description |
| --- | --- |
| `Gaussian` | Standard Gaussian function |
| `exponential` | Exponential function |

* The order of elements of the Reynolds stresses for the vector\-based
condition is "(Rxx Rxy Rxz Ryy Ryz Rzz)" and for the scalar\-based
condition is "R".
* The order of elements of the integral scales for the vector\-based
condition is "(Lxu Lxv Lxw Lyu Lyv Lyw Lzu Lzv Lzw)" and for the
scalar\-based condition is "(Lxi Lyi Lzi)", where \\c x here indicates
the streamwise components and \\c y/z lateral components. The streamwise
components (i.e. \\c x) are Lagrangian time scales in units of seconds
and the remaining components are length scales in units of meters.
* \\c adjustTimeStep\=true option is only supported by
the forward\-stepwise method.
* The default global Cartesian coordinate system "(e1 e2 e3\)"
corresponds to "(x y z)".

## Further information

Tutorial:

* [oneCellThickPlaneChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/turbulentInflow/oneCellThickPlaneChannel)

Source code:

* [turbulentDigitalFilterInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/turbulentDigitalFilterInlet)

API:

* [Foam::turbulentDigitalFilterInletFvPatchField](https://api.openfoam.com/2606/Foam_turbulentDigitalFilterInletFvPatchField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
