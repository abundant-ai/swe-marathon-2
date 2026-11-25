<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmBoundaryLayer -->

# atmBoundaryLayer

## Description

Base class to set log\-law type ground\-normal inlet boundary conditions for
wind velocity and turbulence quantities for homogeneous, two\-dimensional,
dry\-air, equilibrium and neutral atmospheric boundary layer (ABL) modelling.

The ground\-normal profile expressions are due to YGCJ
(refer to references below) whereat RH expressions were generalised:

u\=u∗κln⁡(z−d\+z0z0) u \= \\frac{u^\*}{\\kappa} \\ln \\left( \\frac{z \- d \+ z\_0}{z\_0} \\right)u\=κu∗​ln(z0​z−d\+z0​​)
v\=w\=0 v \= w \= 0v\=w\=0
k\=(u∗)2CμC1ln⁡(z−d\+z0z0)\+C2 k \= \\frac{(u^\*)^2}{\\sqrt{C\_\\mu}}
 \\sqrt{C\_1 \\ln \\left( \\frac{z \- d \+ z\_0}{z\_0} \\right) \+ C\_2}k\=Cμ​​(u∗)2​C1​ln(z0​z−d\+z0​​)\+C2​​
ϵ\=(u∗)3κ(z−d\+z0)C1ln⁡(z−d\+z0z0)\+C2 \\epsilon \= \\frac{(u^\*)^3}{\\kappa (z \- d \+ z\_0\)}
 \\sqrt{C\_1 \\ln \\left( \\frac{z \- d \+ z\_0}{z\_0} \\right) \+ C\_2}ϵ\=κ(z−d\+z0​)(u∗)3​C1​ln(z0​z−d\+z0​​)\+C2​​
ω\=u∗κCμ1z−d\+z0 \\omega \= \\frac{u^\*}{\\kappa \\sqrt{C\_\\mu}} \\frac{1}{z \- d \+ z\_0}ω\=κCμ​​u∗​z−d\+z0​1​
u∗\=urefκln⁡(zref\+z0z0) u^\* \=
 \\frac{u\_{ref} \\kappa}{\\ln\\left(\\frac{z\_{ref} \+ z\_0}{z\_0}\\right)}u∗\=ln(z0​zref​\+z0​​)uref​κ​
where:

| Property | Description |
| --- | --- |
| uuu | Ground\-normal streamwise flow speed profile \[m/s] |
| vvv | Spanwise flow speed \[m/s] |
| www | Ground\-normal flow speed \[m/s] |
| kkk | Ground\-normal turbulent kinetic energy (TKE) profile \[m^2/s^2] |
| ϵ\\epsilonϵ | Ground\-normal TKE dissipation rate profile \[m^2/s^3] |
| ω\\omegaω | Ground\-normal specific dissipation rate profile \[m^2/s^3] |
| u∗u^\*u∗ | Friction velocity \[m/s] |
| κ\\kappaκ | von Kármán constant \[\-] |
| CμC\_\\muCμ​ | Empirical model constant \[\-] |
| zzz | Ground\-normal coordinate component \[m] |
| ddd | Ground\-normal displacement height \[m] |
| z0z\_0z0​ | Aerodynamic roughness length \[m] |
| urefu\_{ref}uref​ | Reference mean streamwise wind speed at zrefz\_{ref}zref​ \[m/s] |
| zrefz\_{ref}zref​ | Reference height being used in u∗u^\*u∗ estimations \[m] |
| C1C\_1C1​ | Curve\-fitting coefficient for YGCJ profiles \[\-] |
| C2C\_2C2​ | Curve\-fitting coefficient for YGCJ profiles \[\-] |

### References

* The ground\-normal profile expressions (tag:RH):

```
Richards, P. J., & Hoxey, R. P. (1993).
Appropriate boundary conditions for computational wind
engineering models using the k-ε turbulence model.
In Computational Wind Engineering 1 (pp. 145-153).
DOI:10.1016/B978-0-444-81688-7.50018-8

```

* Modifications to preserve the profiles downstream (tag:HW):

```
Hargreaves, D. M., & Wright, N. G. (2007).
On the use of the k–ε model in commercial CFD software
to model the neutral atmospheric boundary layer.
Journal of wind engineering and
industrial aerodynamics, 95(5), 355-369.
DOI:10.1016/j.jweia.2006.08.002

```

* Expression generalisations to allow height variation for turbulence quantities (tag:YGCJ):

```
Yang, Y., Gu, M., Chen, S., & Jin, X. (2009).
New inflow boundary conditions for modelling the neutral equilibrium
atmospheric boundary layer in computational wind engineering.
J. of Wind Engineering and Industrial Aerodynamics, 97(2), 88-95.
DOI:10.1016/j.jweia.2008.12.001

```

* The generalised ground\-normal profile expression for omega (tag:YGJ):

```
Yang, Y., Gu, M., & Jin, X., (2009).
New inflow boundary conditions for modelling the
neutral equilibrium atmospheric boundary layer in SST k-ω model.
In: The Seventh Asia-Pacific Conference on Wind Engineering,
November 8-12, Taipei, Taiwan.

```

* Theoretical remarks (tag:E):

```
Emeis, S. (2013).
Wind Energy Meteorology: Atmospheric
Physics for Wind Power Generation.
Springer-Verlag Berlin Heidelberg.
DOI:10.1007/978-3-642-30523-8

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
    flowDir         <vector>;
    zDir            <vector>;
    Uref            <scalar>;
    Zref            <scalar>;
    z0              <scalarField>;
    d               <scalarField>;

    // Optional entries
    kappa           <scalar>;
    Cmu             <scalar>;
    initABL         <bool>;
    phi             <word>;
    C1              <scalar>;
    C2              <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `flowDir` | Flow direction | Function1\<vector\> | yes | \- |
| `zDir` | Ground\-normal direction | Function1\<vector\> | yes | \- |
| `Uref` | Reference mean streamwise flow speed being used in u∗u^\*u∗ estimations \[m/s] | Function1\<scalar\> | yes | \- |
| `Zref` | Reference height being used in u∗u^\*u∗ estimations \[m] | Function1\<scalar\> | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |
| `d` | Displacement height \[m] \- see Notes | PatchFunction1\<scalar\> | yes | \- |
| `kappa` | von Karman constant | scalar | no | 0\.41 |
| `Cmu` | Empirical model constant | scalar | no | 0\.09 |
| `initABL` | Flag to initialise profiles with the theoretical ABL expressions, otherwise use "value" list | bool | no | true |
| `value` | ABL profile content when initABL\=false | scalarList | conditional | \- |
| `phi` | Name of the flux field | word | no | phi |
| `C1` | Curve\-fitting coefficient YGCJ profiles | scalar | no | 0\.0 |
| `C2` | Curve\-fitting coefficient YGCJ profiles | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* Function1\.H
* PatchFunction1\.H

* The RH expressions are special cases of those in YGCJ when `C1=0`
and `C2=1`. Both `C1` and `C2` can be determined by nonlinear fitting
of (YGCJ:Eqs. 19\-20\) with an experimental dataset for `k`. By default,
`atmBoundaryLayerInlet` boundary conditions compute RH expressions.
* `z` is the ground\-normal height relative to the global minimum height
of the inlet patch; therefore, the minimum of `z` is always zero
irrespective of the absolute z\-coordinate of the computational patch.
* The derived ABL expressions automatically satisfy the simplified transport
equation for `k`. Yet the same expressions only satisfy the simplified
transport equation for `epsilon` when the model constants `sigmaEpsilon`
is 1\.11 with `kappa=0.4` (HW:p. 358\).
* `atmBoundaryLayerInlet` boundary conditions inherit `inletOutlet`
traits, so that a given inlet condition can be supplied from all sides of
the domain, e.g. a ground\-normal cylinder domain having a single
inlet/outlet boundary where the changes between inlet and outlet depend
on the wind direction and patch normals, so that any change in inflow
orientation can be handled with the same mesh.
* `d` is the displacement height, and "is relevant for flows over forests
and cities" (E:p. 28\). "The displacement height gives the vertical
displacement of the entire flow regime over areas which are densely covered
with obstacles such as trees or buildings" (E:p. 28\).

## Further information

Tutorial:

* N/A

Source code:

* [atmBoundaryLayer](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/atmBoundaryLayer)

API:

* [Foam::atmBoundaryLayer](https://api.openfoam.com/2606/Foam_atmBoundaryLayer.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
