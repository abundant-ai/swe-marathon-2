<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/pressure -->

# pressure

## Description

The `pressure` function object
provides several methods to convert an input pressure
field into derived forms, including:

* Static pressure, ppp:

p\=ρ pkp \= \\rho \\, p\_kp\=ρpk​
* Total pressure, ptp\_tpt​:

pt\=pref\+p\+0\.5ρ∣u∣2p\_t \= p\_{\\ref} \+ p \+ 0\.5 \\rho \|\\u\|^2pt​\=pref​\+p\+0\.5ρ∣u∣2
* Pressure coefficient, static or total, CpC\_pCp​:

Cp\=p0\.5ρ∞∣u∞∣2C\_p \= \\frac{p}{0\.5 \\rho\_{\\infty} \\mag{\\u\_{\\infty}}^2}Cp​\=0\.5ρ∞​∣u∞​∣2p​
* Isentropic pressure, pip\_ipi​:

pi\=p\[1\+γ−12M2]γγ−1p\_i \= p \\left\[1 \+ \\frac{\\gamma\-1}{2} M^2 \\right]^{\\frac{\\gamma}{\\gamma\-1}}pi​\=p\[1\+2γ−1​M2]γ−1γ​
where:

ρ\\rhoρ
: Density \[kg/m3]

u\\uu
: Velocity \[m/s]

ρinf⁡\\rho\_{\\inf}ρinf​
: Freestream density \[kg/m3]

pinf⁡p\_{\\inf}pinf​
: Freestream pressure \[Pa]

uinf⁡\\u\_{\\inf}uinf​
: Freestream velocity \[m/s]

pkp\_kpk​
: Kinematic pressure (p/rho) \[m2/s2]

psp\_sps​
: Static pressure \[Pa]

p0p\_0p0​
: Total pressure \[Pa]

prefp\_{\\ref}pref​
: Reference pressure level \[Pa]

pip\_ipi​
: Total isentropic pressure

CpC\_pCp​
: Pressure coefficient

Cp0C\_{p\_0}Cp0​​
: Total pressure coefficient

γ\\gammaγ
: Specific heat ratio

For incompressible cases, the kinematic pressure (pressure divided by density)
can be converted to pressure via a user\-specified reference density.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volScalarField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `pressure` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
pressure1
{
    // Mandatory entries (unmodifiable)
    type            pressure;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    mode            <option>;

    // Optional entries (runtime modifiable)
    p               <pName>;
    U               <UName>;
    rho             <rhoName>;
    rhoInf          1.0; // enabled if rho=rhoInf
    pRef            0.0;
    hydroStaticMode none;
    g               (0 -9.81 0); // enabled if hydroStaticMode != none
    hRef            0.0;         // enabled if hydroStaticMode != none
    pInf            0.0;
    UInf            (1 0 0);
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: pressure | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| mode | Calculation mode (see below) | word | yes | \- |
| p | Name of the pressure field | word | no | p |
| U | Name of the velocity field | word | no | U |
| rho | Name of the density field | word | no | rho |
| rhoInf | Freestream density for coefficient calculation | scalar | conditional | \- |
| pRef | Reference pressure for total pressure | scalar | no | 0 |
| hydrostaticMode | Hydrostatic contributions (see below) | word | no | none |
| g | Gravity vector (see below) | vector | no | \- |
| hRef | Reference height (see below) | scalar | no | \- |
| pInf | Freestream pressure for coefficient calculation | scalar | no | \- |
| UInf | Freestream velocity for coefficient calculation | vector | no | \- |

Options for the `mode` entry:

```
static      | static pressure
total       | total pressure
isentropic  | isentropic pressure
staticCoeff | static pressure coefficient
totalCoeff  | total pressure coefficient

```

The `hydrostaticMode` entry provides handling for the term
ρ(g⋅h)\\rho (\\vec{g} \\cdot \\vec{h})ρ(g⋅h) where options include

```
none     | not included
add      | add the term, e.g. to convert from p_rgh to p
subtract | subtract the term, e.g. to convert from p to p_rgh

```

If the `hydrostaticMode` is active, values are also required for
gravity, `g`, and reference height, `hRef`. By default these will be
retrieved from the database. When these values are not available
the user must provide them, e.g.

```
g           (0 -9.81 0);
hRef        0;

```

Default behaviour assumes that the case is compressible. For incompressible
cases, i.e. solved using the kinematic pressure:

pk\=pρ\[m2s−2]p\_k \= \\frac{p}{\\rho} \\qquad \[\\mathrm{m}^2 \\mathrm{s}^{\-2}]pk​\=ρp​\[m2s−2]
The `rho` entry can be used to set the freestream density:

```
rho         rhoInf;
rhoInf      100000;

```

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Usage by the `postProcess` utility is not available.

## Stored properties

### Fields

The derived pressure is stored on the mesh database, using the default name:

* static pressure: `static(p)`
* static pressure coefficient: `static(p)_coeff`
* total pressure: `total(p)`
* total pressure coefficient: `total(p)_coeff`

This can be overridden using the `result` entry.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [pressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/pressure)

API:

* [Foam::functionObjects::pressure](https://api.openfoam.com/2606/Foam_functionObjects_pressure.html)

**History:** Introduced in version [2\.2\.0](https://www.openfoam.com/news/main-news/openfoam-2.2.0)
