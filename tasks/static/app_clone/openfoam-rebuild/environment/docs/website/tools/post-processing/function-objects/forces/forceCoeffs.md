<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/forces/forceCoeffs -->

# Force coefficients

The `forceCoeffs` function object generates aerodynamic force and moment
coefficient data for surfaces and porous regions, with optional:

* inclusion of porous drag
* local co\-ordinate system
* data binning

## Usage

Basic operation of the `forceCoeffs` function object comprises:

```
forceCoeffs1
{
    type            forceCoeffs;
    libs            ("libforces.so");
    patches         (<list of patch names>);
}

```

For more complete control, the full set of input entries includes:

```
forceCoeffs1
{
    // Mandatory entries
    type            forceCoeffs;
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

    // Lift direction
    liftDir         (0 0 1);

    // Drag direction
    dragDir         (1 0 0);

    // Pitch axis
    pitchAxis       (0 1 0);

    // Freestream velocity magnitude [m/s]
    magUInf         30;

    // Reference length [m]
    lRef            1;

    // Reference area [m2]
    Aref            1.75;

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
cases, i.e. solved using the kinematic pressure:

pk\=pρ\[m2s−2] p\_k \= \\frac{p}{\\rho} \\qquad \[\\mathrm{m}^2 \\mathrm{s}^{\-2}]pk​\=ρp​\[m2s−2]

the `rho` entry can be used to set the freestream density:

```
rho         rhoInf;
rhoInf      100000;

```

## Sample output

Text reporting:

* Coefficient data divided into total, pressure,
viscous and porous contributions

```
forceCoeffs forceCoeffs1 write:
    Coefficient	Total	Pressure	Viscous	Internal
    Cd:	0.420059	0.406413	0.0136462	0
    Cd(f):	0.215934	0.208904	0.00703002	0
    Cd(r):	0.204125	0.197509	0.00661615	0
    Cl:	0.0530861	0.0530808	5.34317e-06	0
    Cl(f):	0.195825	0.189931	0.00589387	0
    Cl(r):	-0.142739	-0.13685	-0.00588852	0
    CmPitch:	0.169282	0.163391	0.00589119	0
    CmRoll:	0.00590429	0.00569735	0.000206938	0
    CmYaw:	0.000571337	0.000892135	-0.000320798	0
    Cs:	-0.0133976	-0.0131692	-0.000228412	0
    Cs(f):	-0.00612746	-0.00569246	-0.000435004	0
    Cs(r):	-0.00727014	-0.00747673	0.000206593	0

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `Cm` : total moment coefficient
* `Cd` : total drag coefficient
* `Cl`: total lift coefficient
* `Cl(f)` : total front lift coefficient
* `Cl(r)` : total rear lift coefficient

## Fields

* `forceCoeff` : force coefficients
* `momentCoeff` : moment coefficients

## Further information

Related:

* [forces](../forces.md) function object

Source code:

* [forceCoeffs](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/forces/forceCoeffs)

API:

* [Foam::functionObjects::forceCoeffs](https://api.openfoam.com/2606/Foam_functionObjects_forceCoeffs.html)

Example usage:

* sonicFoam `nacaAirfoil` tutorial:
[nacaAirfoil](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/sonicFoam/RAS/nacaAirfoil)
