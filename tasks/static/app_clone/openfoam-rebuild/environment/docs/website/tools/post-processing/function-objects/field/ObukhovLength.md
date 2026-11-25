<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/ObukhovLength -->

# ObukhovLength

## Description

The `ObukhovLength` function object computes the Obukhov length field
and associated friction velocity field.

When scaled by the ground\-normal height, i.e. `z`, the Obukhov length becomes
a dimensionless stability parameter, i.e. `z/L`, for atmospheric boundary
layer modelling, expressing the relative roles of buoyancy and shear in the
production and dissipation of turbulent kinetic energy.

The model expressions ([56](../../../../references.md#obukhov_atm_1971), Eq. 26\):

u∗\=max⁡(νt∣∇u\+∇uT∣2,ζ) u^\* \= \\sqrt{ \\max \\left(\\nu\_t \\sqrt{\| \\grad{\\u} \+ \\grad{\\u}^T \|^2}, \\zeta \\right)}u∗\=max(νt​∣∇u\+∇uT∣2​,ζ)​
Lo\=−(u∗)3sign(B)κmax⁡(∣B∣,ζ) L\_o \= \- \\frac{(u^\*)^3}{ {sign}(B) \\kappa \\max (\|B\|, \\zeta)}Lo​\=−sign(B)κmax(∣B∣,ζ)(u∗)3​
with

B\=αtβ∇T⋅gρ B \= \\alpha\_t \\beta \\frac{\\grad{T} \\cdot \\vec{g}}{\\rho}B\=αt​βρ∇T⋅g​
where:

u∗u^\*u∗
: Friction velocity, \[m/s]

νt\\nu\_tνt​
: Turbulent viscosity, \[m2/s]

u\\uu
: Velocity, \[m/s]

LoL\_oLo​
: Obukhov length, \[m]

BBB
: Buoyancy production term, \[m2/s3]

αt\\alpha\_tαt​
: Kinematic turbulent thermal conductivity, \[m2/s]/\[kg/m/s]

ρ\\rhoρ
: Density of fluid, \[kg/m3]

β\\betaβ
: Thermal expansion coefficient, \[1/K]

TTT
: Temperature, \[K]

g\\vec{g}g
: Gravitational acceleration, \[m/s2]

ζ\\zetaζ
: A very small number to avoid floating point exceptions, \[\-]

Required fields:

```
U           | Velocity                                 [m/s]
T           | Temperature                              [K]
nut         | Turbulent viscosity                      [m2/s]
alphat      | Kinematic turbulent thermal conductivity [m2/s]/[kg/m/s]
g           | Gravitational acceleration               [m/s2]

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field 1 | volScalarField | `$FOAM_CASE/<time>/<ObukhovLength>` |
| output field 2 | volScalarField | `$FOAM_CASE/<time>/<Ustar>` |

## Usage

Example of the `ObukhovLength` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
ObukhovLength1
{
    // Mandatory entries (unmodifiable)
    type            ObukhovLength;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    U               U;
    result1         ObukhovLength;
    result2         Ustar;
    rhoRef          1.0;
    kappa           0.4;
    beta            3e-3;

    // Optional (inherited) entries
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: ObukhovLength | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| U | Name of the velocity field | word | no | U |
| result1 | Name of the output field for ObukhovLength | word | no | ObukhovLength |
| result2 | Name of the output field for Ustar | word | no | Ustar |
| rhoRef | Reference density (to convert from kinematic to static pressure) | scalar | no | 1\.0 |
| kappa | von Kármán constant | scalar | no | 0\.40 |
| beta | Thermal expansion coefficient | scalar | no | 3e\-3 |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Example by using the `postProcess -func` utility:

```
postProcess -func "ObukhovLength(<UField>)"

```

## Further information

Tutorial:

* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code:

* [ObukhovLength](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/functionObjects/ObukhovLength)

API:

* [Foam::functionObjects::ObukhovLength](https://api.openfoam.com/2606/Foam_functionObjects_ObukhovLength.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
