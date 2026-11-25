<!-- https://doc.openfoam.com/2606/examples/verification-validation/turbulent/plane-channel-flow -->

# Turbulent plane channel flow with smooth walls

## Overview

* Replicates Poletto et al.'s [58](../../../references.md#poletto_new_2013) setup and settings
for [Direct numerical simulation of turbulent channel flow up to Ret\=590](https://doi.org/10.1063/1.869966) [51](../../../references.md#moser_direct_1999)
* References: Van Driest (1956\) [84](../../../references.md#vandriest_turbulent_1956),
Smagorinsky (1963\) [64](../../../references.md#smagorinsky_general_1963),
Kim et al. (1987\) [28](../../../references.md#kim_turbulence_1987),
Moser et al. (1999\) [51](../../../references.md#moser_direct_1999), and
Poletto et al. (2013\) [58](../../../references.md#poletto_new_2013) (Synthetic turbulence
inflow generator)
* See the [resources](plane-channel-flow.md#sec-resources) section for additional data files

**Flow physics:**

* Internal flow
* Moderate Reynolds number
* Spanwise direction: Statistically homogeneous
* Streamwise and channel\-height directions: Statistically developing
* Newtonian, single\-phase, incompressible, non\-reacting

**Solver:**

* [pimpleFoam](../../../tools/processing/solvers/rtm/incompressible/pimpleFoam/index.md)

**Tutorial case:**

* [planeChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/planeChannel)

## Physics and Numerics

**Physical domain:**

* The case is a statistically\-developing internal flow through parallel smooth
walls which are two characteristic\-length apart.
	+ xxx: Longitudinal direction (Mean\-flow direction)
	+ yyy: Vertical direction (Wall\-normal direction)
	+ zzz: Spanwise direction (Statistically homogeneous direction)
	+ OOO: Origin at the left\-bottom corner of the numerical domain

**Physical modelling:**

* Reynolds number based on friction velocity: Reuτ\=∣Uτ∣δ/νfluid\=395\\text{Re}\_{u\_\\tau} \= \\vert \\mathbf{U}\_\\tau \\vert \\delta / \\nu\_\\text{fluid} \= 395Reuτ​​\=∣Uτ​∣δ/νfluid​\=395 \[\-]
	+ (Estimated) Friction velocity: Uτ\=(1\.0,0\.0,0\.0) \\mathbf{U}\_\\tau \= (1\.0, 0\.0, 0\.0\)Uτ​\=(1\.0,0\.0,0\.0), and
	∣Uτ∣\=uτ\=1\.0\\vert \\mathbf{U}\_\\tau \\vert \= u\_\\tau \= 1\.0∣Uτ​∣\=uτ​\=1\.0 \[m⋅s\<sup\>\-1\</sup\>]
	+ Characteristic length (Channel half\-height): δ\=1\.0\\delta \= 1\.0 δ\=1\.0 \[m]
	+ Kinematic viscosity of fluid: νfluid≈0\.002532\\nu\_{\\text{fluid}} \\approx 0\.002532νfluid​≈0\.002532

```
\[m<sup>2</sup>⋅s<sup>-1</sup>\]

```

* Bulk velocity of flow: Ub\=(17\.55,0\.00,0\.00) \\mathbf{U}\_b \= (17\.55, 0\.00, 0\.00\)Ub​\=(17\.55,0\.00,0\.00)

```
\[m⋅s<sup>-1</sup>\]

```

* Turbulence model: [Large eddy simulation](../../../tools/processing/models/turbulence/les.md) with the
[Smagorinsky](../../../tools/processing/models/turbulence/les/rtm/Smagorinsky/index.md) sub\-filter scale model utilising the
[van Driest](../../../tools/processing/models/turbulence/les/delta/rtm/vanDriest/index.md) wall\-damping function. The
sub\-filter scale model constants:
	+ $$ C\_k \\approx 0\.02655 $$
	+ $$ C\_e \= 1\.048 $$
	+ $$ C\_s \\approx 0\.065 $$

```
- \$$ C_s = (C_k {C_k/C_e}^{0.5} )^{0.5} $$

```

**Numerical domain modelling:**

* Shape: Rectangular prism
* Dimensions: (x,y,z)\=(20\.0π,2\.0,π) (x, y, z) \= (20\.0\\pi, 2\.0, \\pi)(x,y,z)\=(20\.0π,2\.0,π) \[m]
* Sketch:

![Numerical domain (not in scale)](data:image/png;base64,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)

**Spatial domain discretisation:**

* Mesh type: Rectangular cuboid mesh
* Mesher: [blockMesh](../../../tools/pre-processing/mesh/generation/blockMesh/index.md)
* Number of nodes, NNN: (Nx,Ny,Nz)\=(500,46,82) (N\_x, N\_y, N\_z) \= (500, 46, 82\)(Nx​,Ny​,Nz​)\=(500,46,82) \[nodes]
* Spatial resolution (Δ)(\\Delta)(Δ) distribution:
	+ Uniform in (x,z)(x, z)(x,z)\-directions
	+ Stretched in (y)(y)(y)\-direction; clustered nearby walls
* Uniform mesh particulars:
	+ Δx\+\=(Δxuτ)/νfluid≈49\.6 \\Delta\_x^\+ \= (\\Delta\_x u\_\\tau )/\\nu\_{\\text{fluid}} \\approx 49\.6Δx\+​\=(Δx​uτ​)/νfluid​≈49\.6 \[\-]
	+ Δz\+≈15\.1 \\Delta\_z^\+ \\approx 15\.1Δz\+​≈15\.1 \[\-]
* Wall\-normal mesh particulars:
	+ Simple grading expansion ratio: 25\.0 \[\-] (From top to bottom wall, the ratio is 0\.04\)
	+ First wall\-normal node height: Δy\+≈1\.1\\Delta\_y^\+ \\approx 1\.1Δy\+​≈1\.1
	+ Mesh details:

![Mesh (Front part)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-2-detail-654-445.png)![Mesh](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-3-detail-654-445.png)
**Temporal domain discretisation:**

* Time\-step size: Δt\=0\.004 \\Delta\_t \= 0\.004Δt​\=0\.004 \[s]
* Estimated [Courant\-Friedrichs\-Lewy](../../../tools/post-processing/function-objects/field/CourantNo.md)
(CFL) number based on ux‾y\+\=392\=20\.133 { \\overline{u\_x} }\_{y^\+ \= 392} \= 20\.133ux​​y\+\=392​\=20\.133\[m⋅s\<sup\>\-1\</sup\>]: CFL ≈0\.64\\approx 0\.64≈0\.64

**Equation discretisation:**

Spatial derivatives and variables:

* Gradient: [Gauss linear](../../../tools/processing/numerics/schemes/divergence/rtm/linear/index.md)
* Divergence: [Gauss](../../../tools/processing/numerics/schemes/gauss-theorem.md) `linear`
* Laplacian: `Gauss linear orthogonal`
* Surface\-normal gradient: [orthogonal](../../../tools/processing/numerics/schemes/sngrad/rtm/orthogonal/index.md)

Temporal derivatives and variables:

* `ddtSchemes`: [backward](../../../tools/processing/numerics/schemes/time/rtm/backward/index.md)

**Numerical boundary conditions:**

* Velocity, U\\mathbf{U}U

| Patch | Condition | Value \[m⋅s\<sup\>\-1\</sup\>] |
| --- | --- | --- |
| Inlet | [turbulentDFSEMInlet](../../../tools/processing/boundary-conditions/rtm/derived/inlet/turbulentDFSEMInlet/index.md) | (17\.55, 0\.00, 0\.00\) |
| Outlet | [inletOutlet](../../../tools/processing/boundary-conditions/rtm/derived/inletOutlet/inletOutlet/index.md) | (0\.0, 0\.0, 0\.0\) |
| Sides (zzz\-dir) | [cyclic](../../../tools/processing/boundary-conditions/rtm/derived/coupled/cyclic/index.md) | \- |
| Walls (yyy\-dir) | [fixedValue](../../../tools/processing/boundary-conditions/rtm/derived/general/fixedValue/index.md) | (0\.0, 0\.0, 0\.0\) |

* Pressure, `p`

| Patch | Condition | Value \[m\<sup\>2\</sup\>⋅s\<sup\>\-2\</sup\>] |
| --- | --- | --- |
| Inlet | [zeroGradient](../../../tools/processing/boundary-conditions/rtm/derived/general/zeroGradient/index.md) | \- |
| Outlet | [fixedValue](../../../tools/processing/boundary-conditions/rtm/derived/general/fixedValue/index.md) | 0\.0 |
| Sides (zzz\-dir) | [cyclic](../../../tools/processing/boundary-conditions/rtm/derived/coupled/cyclic/index.md) | \- |
| Walls (yyy\-dir) | [zeroGradient](../../../tools/processing/boundary-conditions/rtm/derived/general/zeroGradient/index.md) | \- |

* Turbulent kinematic viscosity, `nut` (i.e. νt\\nu\_tνt​)

| Patch | Condition | Value \[m\<sup\>2\</sup\>⋅s\<sup\>\-1\</sup\>] |
| --- | --- | --- |
| Inlet | calculated | \- |
| Outlet | calculated | \- |
| Sides (zzz\-dir) | [cyclic](../../../tools/processing/boundary-conditions/rtm/derived/coupled/cyclic/index.md) | \- |
| Walls (yyy\-dir) | [zeroGradient](../../../tools/processing/boundary-conditions/rtm/derived/general/zeroGradient/index.md) | \- |

**Solution algorithms and solvers:**

* Pressure\-velocity: [PISO](../../../tools/processing/solvers/pressure-velocity/piso.md)
* Parallel decomposition of spatial domain and fields:
[scotch](https://api.openfoam.com/2606/Foam_scotchDecomp.html)
* The bandwidth of the coefficient matrix is minimised by
renumberMesh
* Linear solvers:

| Field | Linear Solver | Smoother | Relative Tolerance |
| --- | --- | --- | --- |
| `U` | [smooth](../../../tools/processing/numerics/solvers/smooth.md) | [GaussSeidel](../../../tools/processing/numerics/solvers/smooth/rtm/gaussSeidel/index.md) | 0\.0 |
| `p` | [GAMG](../../../tools/processing/numerics/solvers/multigrid/rtm/GAMG/index.md) | [GaussSeidel](../../../tools/processing/numerics/solvers/smooth/rtm/gaussSeidel/index.md) | 0\.0 |
| `nuTilda` | [smooth](../../../tools/processing/numerics/solvers/smooth.md) | [GaussSeidel](../../../tools/processing/numerics/solvers/smooth/rtm/gaussSeidel/index.md) | 0\.0 |

**Initialisation and sampling:**

* Computation time for a single domain pass\-through based on Ux‾y\+\=392\=20\.133 { \\overline{U\_x} }\_{y^\+ \= 392} \= 20\.133Ux​​y\+\=392​\=20\.133) \[m\<sup\>2\</sup\>⋅s\<sup\>\-1\</sup\>] ≈3\.121\\approx 3\.121≈3\.121 \[s]
* Initialisation pass\-throughs \= ≈2\.7\\approx 2\.7≈2\.7 [58](../../../references.md#poletto_new_2013)
* Sampling pass\-throughs \= ≈24\.5\\approx 24\.5≈24\.5 [58](../../../references.md#poletto_new_2013)

## Results

**List of metrics:**

* Prescribed vs. reproduced Reynolds stress tensor components at inlet patch
* u′u′‾\\overline{u^\\prime u^\\prime}u′u′ downstream development vs. x/δx/ \\deltax/δ
* v′v′‾\\overline{v^\\prime v^\\prime}v′v′ downstream development vs. x/δx/ \\deltax/δ
* u′v′‾\\overline{u^\\prime v^\\prime}u′v′ downstream development vs. x/δx/ \\deltax/δ
* Surface skin friction coefficient Cf\\mathrm{C}\_fCf​ vs. x/δx/ \\delta x/δ
* Streamwise mean flow speed and Reynolds stress tensor components at
uniform\-interval downstream profiles
* Streamwise vorticity ωx\\omega\_xωx​ at x/δ\=0\.1x/ \\delta \= 0\.1x/δ\=0\.1
* Streamwise vorticity ωx\\omega\_xωx​ at x/δ\=1\.0x/ \\delta \= 1\.0x/δ\=1\.0
* Metrics are time and spanwise averaged
* \<⋅\>\< \\cdot \>\<⋅\> is the time\-averaging operator

![](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-uu.png)![Prescribed vs. reproduced Reynolds stress tensor at inlet patch (Poletto et al., Fig. 4)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-vv.png)![](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-ww.png)![](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-uv.png)![<u'u'>-component of Reynolds stress tensor - Downstream development (Poletto et al., Fig. 14) ](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-Fig14.png)![<v'v'>-component of Reynolds stress tensor - Downstream development (Poletto et al., Fig. 15) ](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-Fig15.png)![<u'v'>-component of Reynolds stress tensor - Downstream development (Poletto et al., Fig. 13)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-Fig13.png)![Longitudinal skin friction coefficient at top patch - Downstream development (Poletto et al., Fig. 9)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-Fig9-top.png)![Longitudinal skin friction coefficient at bottom patch - Downstream development (Poletto et al., Fig. 9)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-Fig9-bottom.png)![Streamwise vorticity component at y/δ=0.05 (Poletto et al., Fig. 11)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-vorticityX01.png)![Streamwise vorticity component at y/δ=1.0 (Poletto et al., Fig. 12)](/img/examples/verification-validation/turbulent/plane-channel-flow/pcf-vorticityX1.png)
## Resources

Note: Links will take you to the \<i\>University of Texas at Austin\</i\> website

### Datasets for verifications (plain text)

Reynolds stress tensor profiles:

* [Numerical (DNS)](http://turbulence.ices.utexas.edu/data/MKM/chan395/profiles/chan395.reystress) [51](../../../references.md#moser_direct_1999)

Mean velocity profiles:

* [Numerical (DNS)](http://turbulence.ices.utexas.edu/data/MKM/chan395/profiles/chan395.means) [51](../../../references.md#moser_direct_1999)

Two\-point velocity correlations (i.e. Auto\- and cross\-correlation functions):

* [Numerical (DNS)](http://turbulence.ices.utexas.edu/data/MKM/chan395/correlations/) [51](../../../references.md#moser_direct_1999)
