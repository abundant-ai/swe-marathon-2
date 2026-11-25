<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/forces/forces -->

# Forces

The `forces` function object generates aerodynamic force and moment
data for surfaces and porous regions, with optional

* inclusion of porous drag
* local co\-ordinate system
* data binning

Forces comprise normal pressure

Fp\=∑iρisf,i(pi−pref) \\vec{F}\_p \= \\sum\_i \\rho\_i \\vec{s}\_{f,i} \\left(p\_i \- p\_{\\ref}\\right)Fp​\=i∑​ρi​sf,i​(pi​−pref​)
and tangential viscous contributions:

Fv\=∑isf,i ∙ (μRdev) \\vec{F}\_v \= \\sum\_i s\_{f,i} \\dprod \\left(\\mu \\tensor{R\_{\\mathrm{dev}}} \\right)Fv​\=i∑​sf,i​∙(μRdev​)
Where ρ\\rhoρ is the density, sf,i\\vec{s}\_{f,i}sf,i​ the face area vector,
ppp the pressureμ\\muμ the dynamic viscosity and
Rdev\\tensor{R\_{\\mathrm{dev}}}Rdev​ the deviatoric stress tensor.

## Usage

Basic operation of the `forces` function object comprises:

```
forces1
{
    type            forces;
    libs            ("libforces.so");
    patches         (<list of patch names>);
}

```

For more complete control, the full set of input entries includes:

```
forces1
{
    // Mandatory entries
    type            forces;
    libs            ("libforces.so");
    patches         (<list of patch names>);

    // Optional entries

    // Field names
    p               p;
    U               U;
    rho             rho;

    // Reference pressure [Pa]
    pRef            0;

    // Include porosity effects?
    porosity        no;

    // Store and write volume field representations of forces and moments
    writeFields     yes;

    // Centre of rotation for moment calculations
    CofR            (0 0 0);

    // Spatial data binning
    // - extents given by the bounds of the input geometry
    binData
    {
        nBin        20;
        direction   (1 0 0);
        cumulative  yes;
    }
}

```

Default behaviour assumes that the case is compressible. For incompressible
cases, i.e. solved using the
[kinematic pressure](../../../processing/solvers/algorithm-kinematic-pressure.md)
the `rho` entry can be used to set the free stream density:

```
rho         rhoInf;
rhoInf      100000;

```

## Sample output

Text reporting:

* integrated force and moment data divided into total, pressure,
viscous and porous contributions

```
Sum of forces
    Total    : xxx
    Pressure : xxx
    Viscous  : xxx
    Porous   : xxx

Sum of moments
    Total    : xxx
    Pressure : xxx
    Viscous  : xxx
    Porous   : xxx

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `normalForce` : total normal force
* `tangentialForce` : total tangential force
* `porousForce` : total porous force
* `normalMoment` : total normal moment
* `tangentialMoment` : total tangential moment
* `porousMoment` : total porous moment

### Fields

Optional storing and writing of force and moment fields:

* `forces` : forces
* `moments` : moments

## Further information

Related:

* [force coefficients](forceCoeffs.md) function object

Source code:

* [forces](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/forces/forces)

API:

* [Foam::functionObjects::forces](https://api.openfoam.com/2606/Foam_functionObjects_forces.html)

Example usage:

* [pimpleFoam](../../../processing/solvers/rtm/incompressible/pimpleFoam.md) `propeller` tutorial:
[propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)
