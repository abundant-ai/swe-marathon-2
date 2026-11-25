<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/outletMachNumberPressure -->

# outletMachNumberPressure

## Description

The `outletMachNumberPressure` is a boundary condition that
maintains a certain subsonic Mach number at an
outlet patch by dynamically adjusting the static outlet pressure. It makes
it possible, for example, to simulate the flow in a preturbine engine
exhaust manifold, without resolving details of the flow inside the turbine.
In general, the flow in a choked nozzle can be non\-trivial and expensive
to simulate.

This formulation is derived from a simple model of the gas flow through
a nozzle with fixed geometry. The nozzle flow is assumed to be quasi\-steady,
1D, isentropic and compressible.

This gives the following general relationship between pressure ratio and
Mach number in any cross section inside the nozzle:

ptotp\=\[1\+k−12  M2]kk−1 \\frac{p\_{tot}}{p}\=\\left\[ 1\+ \\frac{k\-1}{2}\\;M^2 \\right]^{\\frac{k}{k\-1}}pptot​​\=\[1\+2k−1​M2]k−1k​
where the constant ratio of heat capacities is k\=cp/cvk\=c\_p/c\_vk\=cp​/cv​.
The Mach number in the cross section is M\=V/cM\=V/cM\=V/c, where ccc is
the speed of sound and V is the uniform velocity in the streamwise
direction.

Overall pressure difference across the nozzle is

r\=pBack/ptot r \= pBack/p\_{tot}r\=pBack/ptot​
When k\=1\.4k\=1\.4k\=1\.4, the flow in the nozzle throat becomes choked when
r\<0\.5 r\<0\.5r\<0\.5 and non\-choked otherwise. This implementation is not applicable
when r\>\=1r\>\=1r\>\=1 where backflow would occur.

The nozzle model assumption locks the relationship between nozzle cross
sectional areas and Mach numbers. For a choked flow it is only the Mach
number on the outlet patch, MoutletM\_{outlet}Moutlet​, that needs to be stated in the
boundary dictionary.

Care should be taken however to ensure that the entries in the input
dictionary and the CFD geometry satisfy the following equation

c1AoutletA1\=1Moutlet\[1\+k−12Moutlet21\+k−12]k\+12(k−1) c1\\frac{A\_{outlet}}{A\_1}\=\\frac{1}{M\_{outlet}}\\left\[\\frac{1\+\\frac{k\-1}{2}
 M\_{outlet}^2}{1\+\\frac{k\-1}{2}}\\right]^{\\frac{k\+1}{2(k\-1\)}}c1A1​Aoutlet​​\=Moutlet​1​\[1\+2k−1​1\+2k−1​Moutlet2​​]2(k−1)k\+1​
where c1c1c1 compensate for non\-uniform outlet profiles, AoutletA\_{outlet}Aoutlet​
is geometrical outlet patch area and A1A\_1A1​ is assumed nozzle throat
area.

In the non\-choked case the outlet patch Mach number is calculated as

Moutlet\=A1c1  Aoutlet2k−1\[r2k−rk\+1k] M\_{outlet} \=
 \\frac{A\_1}
 {c1\\;A\_{outlet}}
 \\sqrt{\\frac{2}{k\-1}\\left\[r^\\frac{2}{k}\-r^\\frac{k\+1}{k} \\right]}Moutlet​\=c1Aoutlet​A1​​k−12​\[rk2​−rkk\+1​]​
The accompanying boundary conditions for velocity should be
`pressureInletOutletVelocity`.

#### References

```
Fox, R. W., McDonald, A. T., & Mitchell, J. W. (2020).
Fox and McDonald's introduction to fluid mechanics.
John Wiley & Sons.

```

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
    type            outletMachNumberPressure;
    pBack           <scalar>;
    choked          <bool>;

    // Optional entries
    M               <scalar>;
    c1              <scalar>;
    A1              <scalar>;
    phi             <word>;
    rho             <word>;
    U               <word>;
    relax           <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `outletMachNumberPressure` | word | yes | \- |
| `pBack` | Pressure downstream of nozzle | bool | yes | \- |
| `choked` | Defines nozzle conditions | bool | yes | \- |
| `M` | Outlet Mach number | scalar | no | 0 |
| `c1` | Correction factor for non\-uniform profiles | scalar | no | 0 |
| `A1` | Nozzle throat area \[m^2] | scalar | no | 0 |
| `relax` | Underrelaxation of static pressure | scalar | no | 0 |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `U` | Name of velocity field | word | no | U |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [chokedNozzle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/reactingFoam/RAS/chokedNozzle)

Source code:

* [outletMachNumberPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/outletMachNumberPressure)

API:

* [Foam::outletMachNumberPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_outletMachNumberPressureFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
