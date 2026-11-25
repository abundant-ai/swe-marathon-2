<!-- https://www.openfoam.com/news/main-news/openfoam-v2606 -->

QUICK LINKS

[PRE\-PROCESSING](#pre-processing)
[NUMERICS](#numerics)
[SOLVERS AND PHYSICS](#solvers-and-physics)
[POST\-PROCESSING](#post-processing)
[INFRASTRUCTURE](#infrastructure)
[PARALLEL](#parallel)
[PLUGINS](#plugins)
[COMMUNITY](#community)
[ABOUT US](#about-us)

# New OpenFOAM® v2606 release

The OpenFOAM Team is pleased to announce the June 2026 release of OpenFOAM® v2606\. This release extends [OpenFOAM\-v2512](/news/main-news/openfoam-v2512 "New OpenFOAM® v2512 release") features across many areas of the code. The new functionality represents development sponsored by Keysight's customers, internally funded developments, and integration of features and changes from the [OpenFOAM community](/governance/overview "Overview").

OpenFOAM is distributed by Keysight under the [GPL License](http://www.gnu.org/licenses/quick-guide-gplv3.html). In addition to [source code packages](https://gitlab.com/openfoam/core/openfoam/-/blob/master/doc/Build.md) suitable for compilation on a variety of Linux and other POSIX systems, this release also has a number of [pre\-compiled binary packages](https://gitlab.com/openfoam/core/openfoam/-/wikis/precompiled)

* [Ubuntu Linux](https://gitlab.com/openfoam/core/openfoam/-/wikis/precompiled/debian): packaged installation for Ubuntu 24\.04 (LTS), 22\.04 (LTS) and others
* [openSUSE Linux](https://gitlab.com/openfoam/core/openfoam/-/wikis/precompiled/suse): packaged installation for Leap 16\.0, 15\.7, 15\.6
* [Red Hat Linux variants](https://gitlab.com/openfoam/core/openfoam/-/wikis/precompiled/redhat): packaged installation for EPEL 9; Fedora 41, 42
* [apptainer images](https://hub.docker.com/r/opencfd/openfoam-dev/tags): available from Docker Hub as openfoam\-dev:2606\-apptainer and openfoam\-dev:apptainer

Windows users have three options for pre\-compiled packages ([more information](https://gitlab.com/openfoam/core/openfoam/-/wikis/precompiled/windows)):

* Using Windows Subsystem for Linux (based on Ubuntu, openSUSE etc.)
* Native executables with cross\-compilation
* A Docker installation

OpenFOAM apptainer support is provided via description files rather than pre\-assembled images:

* See [packaging/containers](https://gitlab.com/openfoam/packaging/containers)

MacOS users have the option to compile from source, or use Docker containers for pre\-compiled packages ([more information](https://gitlab.com/openfoam/core/openfoam/-/wikis/building#darwin-mac-os)).

## Pre\-processing

 [TOP](#)

* Updated distributedTriSurfaceMesh [more...](/node/681#distributedtrisurfacemesh)
* Improved to the splitMeshRegions utility [more...](/node/681#splitmeshregions)
* New patchDistanceToCell cell source [more...](/node/681#patchdistancetocell)

## Numerics

 [TOP](#)

* Improvements to inverseDistance method in overset grids [more...](/node/682#overset)
* Improved Finite Area [more...](/node/682#finite-area)
* Improved AMI cache: restart [more...](/node/682#ami)

## Solvers and physics

 [TOP](#)

* New two\-equation RANS turbulence model: GEKO [more...](/node/688#geko)
* New Lagrangian patch interaction model: BaiGosman [more...](/node/688#bai-gosman)
* Improved convolution in turbulent digital filter inlet boundary condition [more...](/node/688#turbulent-digital-filter)
* Improved heat diffusion [more...](/node/688#heat-diffusion)

## Post\-processing

 [TOP](#)

* New relative velocity function object [more...](/node/683#relative-velocity)
* New option for polyhedral cell conversion [more...](/node/683#cell-conversion)
* Improved conversion tools [more...](/node/683#conversion)
* Improved surface noise [more...](/node/683#surface-noise)
* New agglomeration visualisation [more...](/node/683#agglomeration)

## Infrastructure

 [TOP](#)

* [Community contribution](/node/687): GPU [more...](/node/684#gpu)
* Coding [more...](/node/684#coding)
* Improved debugging support [more...](/node/684#debugging)
* Porting [more...](/node/684#porting)

## Parallel

 [TOP](#)

* GAMG processor agglomeration : communication\-aware multiple masters [more...](/node/685#gamg)
* Parallel [more...](/node/685#parallel)

## Plugins

 [TOP](#)

* [Community contribution](/node/687): pybFoam [more...](/node/686#pybfoam)
* [Community contribution](/node/687): pyOFTools [more...](/node/686#pyoftools)
* New VTK\-HDF support [more...](/node/686#vtkhdf)

## Community

 [TOP](#)

## About us

 [TOP](#)

OpenFOAM is produced by the core Keysight OpenFOAM team

* Andrew Heather
* Mattijs Janssens
* Mark Olesen
* Prashant Sonakar
* Pawan Ghildiyal
* Kutalmış Berçin
* Matej Forman
* Chiara Pesci
* Martin Lichtmes
* Jiri Polansky
* Niloufar Bordbar
* Vijaya Kumar G
* Swapnil Salokhe
* Matthieu Niess
* Solange Lecat

With wider support from

* the global Keysight Technologies teams

and contributions from

* The [OpenFOAM Community](/news/main-news/openfoam-v2606/community "v2606: OpenFOAM Community")


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/pre-processing -->

QUICK LINKS

[DISTRIBUTEDTRISURFACEMESH](#distributedtrisurfacemesh)
[SPLITMESHREGIONS](#splitmeshregions)
[CREATEPATCH](#create-patch)
[PATCHDISTANCETOCELL](#patchdistancetocell)

# v2606: New and improved pre\-processing

## Updated distributedTriSurfaceMesh

 [TOP](#)

In this release, the `snappyHexMesh` geometry type `distributedTriSurfaceMesh` has been updated with two useful enhancements.

The first change introduces an exclusion bounding box. The utility now calculates a bounding box (`exclusionBb`) that encompasses all the triangles it holds. For any query that falls fully inside this bounding box, the geometry can be resolved locally, avoiding excessive remote tests. This optimisation is enabled by default but can be disabled if required:

```
box
{
    file "box.obj";
    type distributedTriSurfaceMesh;

    // Do not calculate exclusion bounding box
    exclusionBb         false;
}
```
The second change allows `distributedTriSurfaceMesh` to behave exactly like `triSurfaceMesh` while loading the geometry only on selected processors:

```
box
{
    file "box.obj";
    type distributedTriSurfaceMesh;

    // Send whole surface to master of each node
    distributionType    nodeMaster;
}
```
With this configuration, per\-node memory usage is reduced, at the cost of additional communication and a potential bottleneck on the processor holding the geometry. The default behaviour is to designate one master processor per node, determined by hostname. Optionally, the number of processors sharing a master can be adjusted using the `nProcessorsPerMaster` setting.

**Tutorials**

* [$FOAM\_TUTORIALS/mesh/snappyHexMesh/distributedTriSurfaceMesh](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/mesh/snappyHexMesh/distributedTriSurfaceMesh)

**Source code**

* [$FOAM\_SRC/parallel/distributed/distributedTriSurfaceMesh/distributedTriSurfaceMesh.H](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/parallel/distributed/distributedTriSurfaceMesh/distributedTriSurfaceMesh.H)

**Merge request**

* [MR!844](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/844)

## Improved to the splitMeshRegions utility

 [TOP](#)

The `splitMeshRegions` utility has been improved with two new options.

##### customRegionNames

When using `splitMeshRegions` with the `combineZones` option, a group of cell zones can be collected into a single region. For example, given zones `zoneA`, `zoneB`, `zoneC`, and `zoneD`, the `combineZones` option can place `zoneA` and `zoneB` into one region and `zoneC` and `zoneD` into another. However, the combined region names are generated by concatenating the cell zone names, e.g. `zoneA_zoneB` and `zoneC_zoneD`. As the number of cell zones in a region grows, these names can become unwieldy.

The new `customRegionNames` option allows explicit names to be assigned to cell zone clusters when using `combineZones`:

```
splitMeshRegions -cellZonesOnly -combineZones '((zoneA zoneB)(zoneC zoneD))' -customRegionNames '(regionX regionY)'
```
##### useSelectedFaceZones

The existing `useFaceZones` option subdivides the inter\-region interface into multiple patches corresponding to all face zones. The new `useSelectedFaceZones` option provides more control by subdividing the inter\-region interfaces into patches corresponding only to a specified subset of face zones.

**Source code**

* [$FOAM\_UTILITIES/mesh/manipulation/splitMeshRegions](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/applications/utilities/mesh/manipulation/splitMeshRegions)

**Merge request**

* [Merge request \#795](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/795)

## New patchDistanceToCell cell source

 [TOP](#)

OpenFOAM provides `patchToCell` to select cells directly adjacent to named patches, and geometric sources such as `boxToCell` and `sphereToCell` for shape\-based regions. Until now there was no way to select cells within a distance band from one or more patches using the same geometric distance algorithm as turbulence wall\-distance calculations.

The `patchDistanceToCell` topoSet cell source has been added to fill that gap for mesh setup, refinement zones, source terms, and post\-processing cell sets.

Near\-wall and annular\-band cell sets can be configured as follows:

```
actions
(
    {
        name    nearWall;
        type    cellSet;
        action  new;
        source  patchDistanceToCell;
        patch   movingWall;
        distance 0.02;
    }

    {
        name    wallBand;
        type    cellSet;
        action  new;
        source  patchDistanceToCell;
        patches (movingWall fixedWalls);
        minDistance 0.01;
        distance 0.04;
    }
);
```
**Source code**

* [$FOAM\_SRC/meshTools/topoSet/cellSources/patchDistanceToCell](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/meshTools/topoSet/cellSources/patchDistanceToCell)

**Merge request**

* [Merge request \#831](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/831)

**Tutorial**

* [$FOAM\_TUTORIALS/incompressible/pisoFoam/RAS/cavity](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

**Issue**

* [Issue \#3503](https://gitlab.com/openfoam/core/openfoam/-/issues/3503)


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/numerics -->

QUICK LINKS

[OVERSET](#overset)
[FINITE AREA](#finite-area)
[AMI](#ami)

# v2606: New and improved numerics

## Improvements to inverseDistance method in overset grids

 [TOP](#)

The inverse\-distance weighted cell\-cell stencil for overset meshes has been made more robust in two key areas.

**Fringe\-to\-fringe cascade prevention:** `OVERSET` fringe cells are now pre\-promoted to `INTERPOLATED` before the donor\-search phase. This prevents fringe cells from being selected as donors for other `OVERSET` acceptors, which previously could create unsafe donor chains and crash the interpolation. Even when `allowInterpolatedDonors` is set to `true`, this guard takes precedence, as fringe\-to\-fringe donation is always unsafe.

**Empty\-stencil protection:** When a donor cell becomes a `HOLE` after the donor\-marking phase, e.g. via `markPatchesAsHoles`, the acceptor cell was previously left as `INTERPOLATED` with an empty stencil, causing the interpolation to crash. Multiple defensive checks have been added to detect and demote such cells to `HOLE`, ensuring the stencil remains consistent. Rare edge cases where the stencil is lost during compaction or map redistribution are also handled.

The result is a more robust overset interpolation that handles complex topological transitions without crashing, particularly in cases with overlapping regions where hole\-cutting and donor search interact closely.

**Source code**

* [$FOAM\_SRC/overset/cellCellStencil/inverseDistance](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/overset/cellCellStencil/inverseDistance)

## Improved Finite Area

 [TOP](#)

This release completes the extension of finite\-area support to handle multiple areas, building on work that was started as part of the [OpenFOAM\-v2512](/news/main-news/openfoam-v2512 "New OpenFOAM® v2512 release") release.

Multiple area support allows different finite\-area physics to be defined for different parts of the volume. For example, different two\-dimensional thermal shells can be applied to some boundary areas while a film shell is applied to another boundary of the same volume. This is especially useful because it allows finite\-area physics solvers to be embedded directly as part of the volume boundary conditions, e.g. thermal shells.

The changes to the setup have been made to be backwards compatible. If there is only a single (default) region, the setup is as before. When multiple area regions are involved, the setup is analogous to multi\-region cases, except that each volume region can now have multiple finite\-area definitions. The tutorial `hotRoomWithThermalShell.multi-area` provides a straightforward introduction to this setup.

In this release, the edge field handling has been updated to properly preserve the flux orientation and edge flipping in parallel. This is now applied consistently through the various decomposition, reconstruction, and redistribution tools. Existing parallel cases should continue to run, as the tooling automatically detects any existing or missing edge flipping addressing. However, newly created `edgeProcAddressing` will not generally be usable with older versions of OpenFOAM.

The previous release already added multi\-area support for decomposition and reconstruction as well as a number of post\-processing tools. This release extends that support to parallel redistribution as well.

For diagnostics, the `foamToVTK` utility now also supports edge field output, and the VTK diagnostics output has been extended for both `checkFaMesh` and `makeFaMesh`.

## Improved AMI cache: restart

 [TOP](#)

AMI caching was introduced in version v2512, providing a potential performance boost for rotating mesh cases. It works by caching the interpolation weights and addressing for re\-use across multiple rotations, saving the assembly cost that would otherwise include multiple parallel reductions and limit scaling performance.

In some workflows it is desirable to clear the cache, e.g. when adopting different time\-step strategies.

This is now available as a single\-shot control when specifying AMI patches:

```
AMI1
{
    cacheSize        <size>;
    cacheRestartTime <time>;
}
```
When `time >= cacheRestartTime`, the cache is cleared and subsequently rebuilt on further evaluations.

Future releases may include multiple restart options depending on requirements.

**Source code**

* [$FOAM\_SRC/meshTools/AMIInterpolation](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/meshTools/AMIInterpolation)


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/solvers-and-physics -->

QUICK LINKS

[GEKO](#geko)
[BAI\-GOSMAN](#bai-gosman)
[TURBULENT DIGITAL FILTER](#turbulent-digital-filter)
[HEAT DIFFUSION](#heat-diffusion)

# v2606: New and improved solvers and physics

## New two\-equation RANS turbulence model: GEKO

 [TOP](#)

OpenFOAM currently offers several widely used RANS turbulence closure models, e.g. `SpalartAllmaras`, `kEpsilon` variants, and `kOmegaSST`. Each model has its strengths and weaknesses, and the most appropriate choice for a given application is often determined by running multiple models against a subset of the potential flow configurations.

However, switching between models can force users to trade accuracy between flow classes, e.g. between boundary layers and free\-shear flows, and this often complicates workflows.

To improve workflow flexibility, the Generalised k\-omega Two\-Equation Turbulence Model (`GEKO`) has been identified as a promising generic RANS closure and has been implemented based on the work of [Menter \&](https://doi.org/10.2514/1.J065678) [Matyushenko](https://doi.org/10.2514/1.J065393)[, 2025](https://doi.org/10.2514/1.J065678) for both incompressible and compressible applications.

GEKO consolidates the two\-equation turbulence models into a single framework by providing four independent free coefficients that target different physics:

* `CSEP`: to optimise flow separation from smooth surfaces, such as boundary layers.
* `CNW`: to optimise flows in non\-equilibrium near\-wall regions, such as heat transfer and skin friction.
* `CMIX`: to optimise spreading rates for free flows.
* `CJET`: to optimise round jet flows.

The implementation provides:

* **Wall\-distance\-free variant** (`wallDistanceFree`).
* **Production limiter** for `k` (`productionLimiter`, default on).
* **Kato\-Launder stagnation correction** (`katoLaunder`).
* **Dilatation correction** in the Reynolds stress tensor (`dilatationCorrection`).
* **Four calibration coefficient fields** – `CSEP`, `CNW`, `CMIX`, `CJET` – each readable as a uniform scalar or spatial field, with optional diagnostic output via `writeCalibrationFields`.
* **Machine\-learning augmentation** (`machineLearning`) via optional `Ck` and `Comega` source terms.
* **Realizability limiter** on `nut`.

The model has been verified against canonical flows:

* Equilibrium boundary layer in a strong adverse pressure gradient over a smooth\-wall flat plate (Skare \& Krogstad, 1994\).
* Free\-shear mixing\-layer flow (Bell \& Mehta, 1990\).
* Zero\-pressure\-gradient smooth\-wall flat plate (Wieghardt \& Tillmann, 1951\).
* Backward\-facing step flow (Driver \& Seegmiller, 1985\).
* CS0 Diffuser flow (Driver, 1991\).
* Axisymmetric transonic bump flow (Bachalo \& Johnson, 1986\).

The following plots show the effect of varying `CMIX` on the self\-similar velocity and turbulent\-kinetic\-energy profiles for the mixing\-layer flow:

![](/sites/default/files/prg/editor/1823/solver-physics-geko-ux-profile.png)![](/sites/default/files/prg/editor/1823/solver-physics-geko-k-profile.png)**Source code**

* [$FOAM\_SRC/TurbulenceModels/turbulenceModels/RAS/GEKO/GEKO.H](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/RAS/GEKO/GEKO.H)

**Merge request**

* [MR!819](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/829)

**References**

```
    Menter, F. R., & Matyushenko, A. (2025).
    Generalized k−omega (GEKO) Two-Equation Turbulence Model.
    AIAA Journal, 63(11), 4590-4606.
    DOI:10.2514/1.J065678
```

## New Lagrangian patch interaction model: BaiGosman

 [TOP](#)

OpenFOAM already provides Bai\-style spray impingement physics through the `splashBai` interaction in the `kinematicSurfaceFilm` surface\-film model. That pathway couples droplet\-wall interaction to a resolved or modelled liquid film on the wall, which is appropriate when film dynamics matter but adds modelling and setup overhead when only direct parcel\-wall impingement is needed.

The `BaiGosman` interaction type has been added to the `localInteraction` patch\-interaction model, based on the Bai\-Gosman spray impingement framework (Bai \& Gosman, 1996\). It exposes the same class of adhesion, rebound, and splash outcomes on a patch\-by\-patch basis for thermo, reacting, and spray Lagrangian clouds, without requiring `surfaceFilmModel` to be enabled.

The implementation provides:

* Per\-patch `BaiGosman` type in `localInteractionCoeffs`.
* The parcel type must expose `T()` and `rho()`, and the cloud database must register `SLGThermo` with at least one liquid component.
* Temperature\-dependent regimes: below `Tmelt`, viscoelastic rebound or adhesion; above `Tmelt`, Weber\- and Ohnesorge\-gated splash with dry\- or wet\-wall treatment controlled by the `dry` switch.
* Secondary splash parcels: stochastic diameter distribution, sampled splash direction, and immediate injection into the owner cloud.

A wall patch can be configured as follows:

```
localInteractionCoeffs
{
    patches
    (
        walls
        {
            type            BaiGosman;
            dry             true;
            Tmelt           400;
            Wec             200;
            parcelsPerSplash 5;
            Adry            2630;
            Awet            1320;
            Cf              0.7;
        }

        outlet
        {
            type escape;
        }
    );

    ...
}
```
The model reproduces the Bai\-Gosman impingement regimes of adhesion, rebound, and splash. Secondary splash droplet energetics use the wall\-normal incident kinetic energy, consistent with the formulation applied to `ThermoSurfaceFilm`.

**Source code**

* [$FOAM\_SRC/lagrangian/intermediate/submodels/Kinematic/PatchInteractionModel/LocalInteraction/BaiGosman.H](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/lagrangian/intermediate/submodels/Kinematic/PatchInteractionModel/LocalInteraction/BaiGosman.H)
* [$FOAM\_SRC/lagrangian/intermediate/submodels/Kinematic/PatchInteractionModel/LocalInteraction/LocalInteraction.H](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/lagrangian/intermediate/submodels/Kinematic/PatchInteractionModel/LocalInteraction/LocalInteraction.H)

**Merge request**

* [Merge request \#838](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/838)

**References**

```
    Bai, C. & Gosman, A., (1996).
    Mathematical Modelling of Wall Films Formed by Impinging Sprays.
    International Congress & Exposition, Detroit, Michigan, United States.
```

## Improved convolution in turbulent digital filter inlet boundary condition

 [TOP](#)

The `turbulentDigitalFilterInlet` boundary condition generates synthetic turbulence\-like inlet time series for LES and DES using the digital\-filter method (DFM) or the forward\-stepwise method (FSM). The convolution that embeds two\-point correlations is performed inside `IntegralScaleBox`. In the previous implementation, random\-field generation and convolution ran only on the master MPI rank, which made that step a serial bottleneck in parallel runs.

The convolution in `IntegralScaleBox` has been parallelised so that generation\-plane work is distributed across MPI ranks. Existing dictionary syntax is unchanged and simulation output remains consistent with the serial implementation. An optional `seed` entry can be used to control reproducibility across restarts and mesh redistribution.

The change eliminates the single\-processor convolution bottleneck and delivers approximately 15%\-35% speedup of the `turbulentInflow` tutorial simulation.

**Source code**

* [$FOAM\_SRC/finiteVolume/fields/fvPatchFields/derived/turbulentDigitalFilterInlet/IntegralScaleBox](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/turbulentDigitalFilterInlet/IntegralScaleBox)
* [$FOAM\_SRC/finiteVolume/fields/fvPatchFields/derived/turbulentDigitalFilterInlet](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/turbulentDigitalFilterInlet)

**Merge request**

* [Merge request \#840](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/840)

## Improved heat diffusion

 [TOP](#)

The `pureZoneMixture` model in `thermophysicalProperties` allows cell\-zone\-specific thermal properties to be defined. In this release, a bug in the heat flux formulation for solid solvers (`solidFoam` and conjugate heat transfer solvers) has been corrected.

For solids with `isotropic` thermal conductivity, harmonic interpolation should be used in the laplacian schemes for `alpha` and `kappa` to obtain a consistent heat flux at the interface between two cell zones with different material properties, e.g.:

```
laplacianSchemes
{
    laplacian(alpha,h)      Gauss harmonic limited corrected 0.5;
    laplacian(kappa,h)      Gauss harmonic limited corrected 0.5;
}
```
For solids with `anisotropic` thermal conductivity, `alpha` and `kappa` are tensors and the harmonic interpolation scheme is not directly available. Linear interpolation should be used instead:

```
laplacianSchemes
{
    laplacian(alpha,h)      Gauss linear limited corrected 0.5;
    laplacian(kappa,h)      Gauss linear limited corrected 0.5;
}
```
To ensure a consistent heat flux at the interface between two cell zones, the solver automatically applies harmonic interpolation to the face\-normal component of the tensors, even when the `linear` scheme is specified in `laplacianSchemes`. Linear interpolation is applied to the off\-diagonal parts of the `alpha` and `kappa` tensors.

**Source code**

* [$FOAM\_SRC/thermophysicalModels/solidThermo/solidThermo](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/thermophysicalModels/solidThermo/solidThermo)

**Merge request**

* [Merge request \#842](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/842)

**Tutorial**

* [$FOAM\_TUTORIALS/heatTransfer/solidFoam/multiSolidWithAnisoConduction](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/heatTransfer/solidFoam/multiSolidWithAnisoConduction)


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/post-processing -->

QUICK LINKS

[RELATIVE VELOCITY](#relative-velocity)
[CELL CONVERSION](#cell-conversion)
[CONVERSION](#conversion)
[SURFACE NOISE](#surface-noise)
[AGGLOMERATION](#agglomeration)

# v2606: New and improved post\-processing

## New relative velocity function object

 [TOP](#)

The new `relativeVelocity` function object computes a relative velocity field for rotating cases. Three rotation modes are supported.

* `specified` allows the user to define one or more rotation zones directly:

```
rotationMode    specified;

specified   // single zone
{
    origin  (0 0 0);    // Rotation around centre line
    axis    (1 0 0);
    n       -25;        // [rev/sec]  (-ve: it is a left-hand propeller)

    zone    innerCylinderSmall;
}
```
* `MRF` references an existing moving reference frame definition:

```
rotationMode    MRF;
```
* `solidBodyRotation` applies a solid body rotation using a `rotatingMotion` definition (cell zones only):

```
rotationMode    solidBodyRotation;
```

Since relative motions can be composed from different cell zones, the function object provides control over how the background cells (those not belonging to any rotation zone) are treated. In most cases this is simply zero velocity, but the user can instead start from a copy of the original velocity field, or specify a custom mask value for untouched cells.

**Source code**

* [$FOAM\_SRC/functionObjects/field/relativeVelocity](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/functionObjects/field/relativeVelocity)

**Tutorials**

* [$FOAM\_TUTORIALS/incompressible/pimpleFoam/RAS/propeller1/system/relativeVelocity](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller1/system/relativeVelocity)
* [$FOAM\_TUTORIALS/incompressible/simpleFoam/mixerVessel2D/system/relativeVelocity](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/mixerVessel2D/system/relativeVelocity)
* [$FOAM\_TUTORIALS/incompressible/pimpleFoam/RAS/propeller/system/relativeVelocity](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller/system/relativeVelocity)

## New option for polyhedral cell conversion

 [TOP](#)

The `cellDecomposer` function object decomposes cells into basic shapes and maps selected fields onto them (similar to `mapFields`). In this release, the functionality has been extended to allow faces to be split without splitting the cells themselves. This can be very beneficial when interfacing with an externally defined triangle mesh using AMI, as it guarantees that the face uses exactly the same geometry as the triangle mesh.

A typical configuration to convert faces into face\-centre triangles is shown below:

```
functions
{
    cellDecomposer
    {
        type            cellDecomposer;
        libs            (fieldFunctionObjects);
        fields          ();
        mapRegion       tetMesh;

        // How to decompose faces
        decomposeType   faceCentre;

        // Cell set to decompose
        selectionMode   cellSet;
        cellSet         dummy;  // empty set

        // Face set to decompose
        faceSelectionMode faceSet;
        faceSet         facesToDecompose;
    }
}
```
This reads in a cell set `dummy` and a face set `facesToDecompose`. Both can be generated using the `topoSet` application. In this particular case the cell set is empty and the face set contains all faces of a chosen patch:

```
{
    name    dummy;
    type    cellSet;
    action  clear;
}
{
    name    facesToDecompose;
    type    faceSet;
    action  patchToFace;
    patch   missingCorner;
}
```
The image below illustrates the effect on the `missingCorner` tutorial, where the quad faces of one patch have been converted into triangles.

![](/sites/default/files/styles/full_width/public/prg/editor/1850/post-processing-cell-decomposer.png?itok=2QRyJX41)**Source code**

* [$FOAM\_SRC/functionObjects/field/cellDecomposer](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/dynamicMesh/polyTopoChange/polyTopoChange/cellDecomposer.H)

**Tutorial**

* [$FOAM\_TUTORIALS/mesh/polyDualMesh/missingCorner](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/mesh/polyDualMesh/missingCorner)

**Issue**

* [Issue \#3529](https://gitlab.com/openfoam/core/openfoam/-/issues/3529)

## Improved conversion tools

 [TOP](#)

VTK volume geometry output (e.g. from `foamToVTK` or the `vtkWrite` function object) no longer shows artefacts at processor boundaries. This clean\-up was already in place for Ensight output, and the VTK volume infrastructure now includes an equivalent topological point merge to remove these processor boundary artefacts.

Both the Ensight and VTK conversions now also accept a `-base-name` option when used as utilities, or a `baseName` property when used as function objects. This allows an alternative base or stem name for output files that is independent of the case name.

The `foamToEnsight` and `foamToVTK` utilities now properly support absolute output paths. This is particularly useful when running with distributed roots, as it allows output to be directed to a common directory such as an NFS\-mounted location.

## Improved surface noise

 [TOP](#)

The surface noise utility has been extended to process surface data that contains no geometric surface information. This is admittedly an unusual concept, but it addresses a genuine need: for externally sampled data, pressures are sometimes only available as values at face centres without any accompanying geometrical data. It is now possible to specify that the input data corresponds to zero\-dimensional elements (a `point` element in Ensight terminology, or a `vertex` element in VTK terminology), and the surface noise processing will handle them accordingly.

The underlying changes to the surface readers and writers are not currently available to regular surface sampling, but could be considered for a future release if there is sufficient interest.

In addition, thanks to a contribution from Robert Perry, the Ensight `collatedTime` writing mode for `surfaceNoise` now correctly retains the writer between loops, ensuring proper collating behaviour.

## New agglomeration visualisation

 [TOP](#)

The quality of field agglomeration has a significant effect on GAMG solver performance. The solver is particularly effective at solving the pressure equation, which tends to dominate steady\-state run times.

The new `agglomerationInfo` function object enables users to create volume fields where agglomeration regions are coloured, providing a straightforward means to visualise the agglomeration structure (commonly referred to as “blobs”).

The function object is typically specified as follows:

```
agglom1
{
    type            agglomerationInfo;
    libs            (utilityFunctionObjects);
    writeControl    writeTime;
}
```
Example images are shown below:

![](/sites/default/files/styles/full_width/public/prg/editor/1865/post-processing-elbow-agglom.png?itok=PmtpMC9o)The agglomeration table is also written to file.

**Source code**

* [$FOAM\_SRC/functionObjects/utilities/agglomerationInfo](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/functionObjects/utilities/agglomerationInfo)


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/infrastructure -->

QUICK LINKS

[GPU](#gpu)
[CODING](#coding)
[DEBUGGING](#debugging)
[PORTING](#porting)

# v2606: New and improved infrastructure

## Community contribution: GPU

 [TOP](#)

This is the first release to support GPU offloading. It uses the C\+\+17/20 `std::execution` policy to automatically run loops in parallel across multiple execution units, which may be GPU devices or cores sharing memory.

##### Background

In modern computer architectures, performance is increasingly limited not by raw computation but by the speed at which data can be transferred from memory to compute units. This work builds on previous GPU porting efforts; for the latest effort, Keysight/OpenCFD teamed up with the UK Science and Technology Facility Council (STFC), Exeter University, and major hardware providers (AMD and Nvidia) to apply modern C\+\+ constructs to the most performance\-critical parts of the code. The main areas addressed are:

* using algorithms that are not order\-dependent and do not cause race conditions, e.g. cell\-based rather than face\-based loops
* offloading loops wherever possible using C\+\+17 execution policies
* allocating memory where it is needed, using a memory pool backed by Umpire
* keeping changes at the lowest level so that the user\-facing API is unaffected (field algebra, linear solvers, boundary evaluation)
* avoiding allocation of intermediate fields, e.g. by interpolating on\-the\-fly rather than creating an intermediate interpolated field, using expression templating

Thanks to:

* STFC: Jony Castagna, Mayank Kumar
* Exeter University: Gavin Tabor, Liam Berrisford
* AMD: Leopold Grinsberg, Kumar Saurabh
* Nvidia: Filippo Spiga, Matthew Martineau, Stan Posey; supplying hardware

##### Results

Even as a first implementation, the results are encouraging. The graph below shows the speed\-up relative to a high\-end 32\-core CPU (Intel Xeon Gold 6448Y).

![](/sites/default/files/styles/full_width/public/prg/editor/1861/speedup_cavity3D_PCG_Intel.png?itok=XA-ep8L2)Memory management is critical. OpenFOAM uses UMPIRE to control where memory chunks reside and ensure efficient access for both CPU and GPU. This remains important even on architectures with unified memory such as GH100 or MI300A.

With a more complex linear solver configuration using GAMG and a specialised smoother, good speed\-ups are achievable for larger cases. Please note that similar speed\-ups should be possible on the MI300A and the performance is still evolving:

![](/sites/default/files/styles/full_width/public/prg/editor/1861/speedup_cavity3D_sGS-GAMG_Intel.png?itok=gvVhnks8)In the current state, there is no patch fusing, so every patch is handled separately. This causes noticeably worse performance for cases with large numbers of patches:

![](/sites/default/files/styles/full_width/public/prg/editor/1861/speedup_motorbike_PCG_Intel.png?itok=hYXamPjZ)The current results are far from the theoretical maximum. Active work continues on patch merging (either built\-in or as a pre\-processing step), greater operation merging (kernels ideally perform complex operations with few intermediates), and avoiding intermediate fields.

##### Risks

* Do not use explicitly serial linear solver routines such as `DIC`, `DILU`, `GaussSeidel`, or `symGaussSeidel`. Use `GAMG` with `twoStageGaussSeidel` as a smoother instead.
* The parallelisation used in the GPU version introduces non\-deterministic behaviour: the ordering of operations can vary from run to run, and the loop structure may differ from the CPU version (e.g. over cells rather than faces). This affects the truncation error, so results will be slightly different compared to CPU runs.
* GPU parallelisation and offloading is a compile\-time option, packaged as a new architecture so that the same source tree can be compiled for either CPU or GPU.
* The current GPU work is still on a separate development track and may be slightly behind the main development line. Care has been taken to ensure that the GPU version behaves identically to the CPU version unless compiled for GPU.
* Using CPU threading (`-stdpar=multicore`) is not properly supported (work\-in\-progress)

**Cases**

* Selected cases from the [HPC committee](https://develop.openfoam.com/committees/hpc/-/tree/develop) have been used for testing

**Source code**

* The code is made available as a branch on a development repository here: [source code](https://gitlab.com/openfoam/gpu/openfoam-ecse)
* Please see the [repo's wiki](https://gitlab.com/openfoam/gpu/openfoam-ecse/-/wikis/home) and associated guides to get started quickly
* After further testing and feedback from the Community we intend to integrate the code in the OpenFOAM v2612 release

## Coding

 [TOP](#)

As part of the ongoing modernisation of the codebase, more methods are now `constexpr` and `noexcept`, which assists the compiler when targeting offloading architectures.

Some of the basic OpenFOAM types (`FixedList`, `Pair`, `Tuple2`, `edge`, and others) now also support C\+\+17 structured bindings, enabling more natural and expressive code. For example:

```
    auto [minId, maxId] = findMinMax_locations(fld)
```
Various list type detection traits (e.g. `is_dynamiclist_v`, `is_fixedlist_v`, `is_indirectlist_v`) have been added to assist with template code.

Some C\+\+20 type traits (e.g. `remove_cvref`, `type_identity`) have been backported to simplify complex template code. The `stdFoam::is_template_base_of_v` provides a functional equivalent of `std::is_base_of` that handles templated classes. Other additions such as `vectorspace_data()` simplify component\-wise handling in templated code.

## Improved debugging support

 [TOP](#)

Debugging on macOS has become easier with new internal handling of the error `printStack` function, which now uses the `atos` utility. This replaces the older `addr2line` replacement that stopped working correctly on more recent macOS versions.

For general programming and debugging, a new `error::demangle()` function is available that returns symbol names in human\-readable form.

To help track down memory hotspots, two high\-level methods are now available for collecting the memory high\-water mark on a per\-node basis.

The `error::list_mem_hwm()` method returns a list of the per\-node summed memory high\-water mark values:

```
    Info<< "mem.hwm = " << flatOutput(error::list_mem_hwm()) << nl;
```
The general macros `PrintMemoryIn(functionName)` and `PrintMemoryInFunction` can be used to report the current per\-node memory high\-water mark as a decorated string in the following form:

```
   [node0][mem.hwm=<digits>](file.cxx:123)
```
The memory high\-water mark is also included in the output when profiling is active.

## Porting

 [TOP](#)

The compilation rules have been extended to support cross\-compilation for Windows ARM64 targets using the llvm\-mingw infrastructure.

The [build\_llvm\-mingwARM64\.Dockerfile](https://gitlab.com/openfoam/packaging/containers/-/blob/main/docker/build_llvm-mingwARM64.Dockerfile) provides an example setup. Note that MPI support for Windows ARM64 is currently quite limited.


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/parallel -->

QUICK LINKS

[GAMG](#gamg)
[PARALLEL](#parallel)

# v2606: New and improved parallel operation

## GAMG processor agglomeration : communication\-aware multiple masters

 [TOP](#)

In this release, `procFaces` has been extended to accept an optional `nMasters` (or `nProcessorsPerMaster`) setting. This enables similar behaviour to `masterCoarsest` by agglomerating processors at the coarsest level until only `nMasters` or fewer remain. With `nMasters 1`, the behaviour is identical to `masterCoarsest` since no inter\-processor boundaries will remain.

##### Effect

Running the `simpleFoam` `pitzDaily` tutorial with the following configuration:

```
p
{
    solver                  GAMG;
    ..
    processorAgglomerator   procFaces;
    nMasters                4;
}
```
With the debug switch enabled:

```
DebugSwitches
{
    GAMGAgglomeration 1;
}
```

```
                              nCells       nFaces/nCells         nInterfaces    nIntFaces/nCells     profile
   Level  nProcs         avg     max         avg     max         avg     max         avg     max         avg
   -----  ------         ---     ---         ---     ---         ---     ---         ---     ---         ---
       0      16         764     770       1.926   1.927         3.5       5      0.1025  0.1299   2.044e+04
       1      16         381     385       1.964   2.143         3.5       5      0.1686  0.2158        8367
       2      16         189     192       2.292   2.774         3.5       5      0.2689   0.349        3062
       3      16          93      96       2.321   2.645         3.5       5      0.4439  0.5532        1028
       4      16          45      47        2.33   2.489         3.5       5      0.6251  0.8043         362
       5       4          89      90       2.497   2.596         1.5       2      0.2982  0.4432       902.5
       6       4          41      43       2.298   2.429         1.5       2      0.4132    0.65       272.2
```
##### Master\-coarsest with compact masters

In this release, masters can be forced to be allocated compactly using the new `compactMasters` option:

```
p
{
    solver                  GAMG;
    ..
    processorAgglomerator   masterCoarsest;
    nMasters                4;
    compactMasters          true;
}
```
In a case with 16 processors and 4 masters, the default master allocation places masters on processors 0, 4, 8, and 12 (visible with the `masterCoarsest` debug switch):

```
  master  nProcs  procIDs
  0       4       (1 2 3)
  4       4       (5 6 7)
  8       4       (9 10 11)
  12      4       (13 14 15)
```
With `compactMasters` enabled, masters are assigned to the lowest\-numbered processors:

```
  master  nProcs  procIDs
  0       4       (4 5 6)
  1       4       (7 8 9)
  2       4       (10 11 12)
  3       4       (13 14 15)
```
##### Effect

Without compact masters:

```
                              nCells       nFaces/nCells         nInterfaces    nIntFaces/nCells     profile
   Level  nProcs         avg     max         avg     max         avg     max         avg     max         avg
   -----  ------         ---     ---         ---     ---         ---     ---         ---     ---         ---
       0      16         764     770       1.926   1.927         3.5       5      0.1025  0.1299   2.044e+04
       1      16         381     385       1.964   2.143         3.5       5      0.1686  0.2158        8367
       2      16         189     192       2.292   2.774         3.5       5      0.2689   0.349        3062
       3      16          93      96       2.321   2.645         3.5       5      0.4439  0.5532        1028
       4      16          45      47        2.33   2.489         3.5       5      0.6251  0.8043         362
       5       4          89      90       2.536   2.596         1.5       2      0.2191  0.2889       949.5
       6       4          41      43        2.36   2.429         1.5       2      0.2897     0.4       291.2
```
With compact masters:

```
                              nCells       nFaces/nCells         nInterfaces    nIntFaces/nCells     profile
   Level  nProcs         avg     max         avg     max         avg     max         avg     max         avg
   -----  ------         ---     ---         ---     ---         ---     ---         ---     ---         ---
       0      16         764     770       1.926   1.927         3.5       5      0.1025  0.1299   2.044e+04
       1      16         381     385       1.964   2.143         3.5       5      0.1686  0.2158        8367
       2      16         189     192       2.292   2.774         3.5       5      0.2689   0.349        3062
       3      16          93      96       2.321   2.645         3.5       5      0.4439  0.5532        1028
       4      16          45      47        2.33   2.489         3.5       5      0.6251  0.8043         362
       5       4          89      90       2.319   2.433           3       3       0.653  0.8621       599.8
       6       4          41      43       2.029   2.116           3       3      0.9538   1.268       172.5
```
The compact masters configuration results in more inter\-processor boundaries and a higher profile. For larger agglomerations, e.g. 64 cores, this effect diminishes. However, there is no guarantee that equal\-sized clusters are produced; on large decompositions, clusters of unequal size may still create bottlenecks.

**Source code**

* [$FOAM\_SRC/OpenFOAM/matrices/lduMatrix/solvers/GAMG/GAMGProcAgglomerations/procFacesGAMGProcAgglomeration/procFacesGAMGProcAgglomeration.C](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/solvers/GAMG/GAMGProcAgglomerations/procFacesGAMGProcAgglomeration/procFacesGAMGProcAgglomeration.C)

**Tutorial**

* [$FOAM\_TUTORIALS/compressible/rhoSimpleFoam/squareBendLiq](https://gitlab.com/openfoam/core/openfoam/-/blob/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/squareBendLiq)

**Merge request**

* [Merge request \#818](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/818)

## Parallel

 [TOP](#)

The Pstream interface to MPI includes several improvements in this release:

* `probeMessage()`: simplified parameters for a regular `MPI_Probe`.
* `probeMessages()`: probe and return sizes from multiple sources simultaneously.

The `IPstream` (input/receive stream) can now be called with a “receive from any” mode, and its receive buffer can also be released. This enables algorithms to use `IPstream` to probe and receive, then recover the buffer for forwarding or storage with delayed deserialisation.

Additional `align`, `tell`, `seek`, and other methods on the input and output Pstreams allow them to be used for composite output with rewriting, enabling more flexible aggregated data handling.

##### Reduced MPI overhead in field function objects

The function objects `fieldExtent`, `fieldMinMax`, and `fieldStatistics` have been updated to significantly reduce the overall number of MPI operations and lower memory overhead. Although these function objects are not in critical code paths, they were selected as initial candidates for assessing the types of hidden overheads that remain in the code. The key improvements are:

* the intermediate volume field required for the `mag()` operation is avoided in most cases
* bounding box reductions are now bundled together, resulting in exactly two MPI reductions instead of `2*(nPatches+1)`
* `fieldMinMax` and `fieldStatistics` now use a single `MPI_AllGather` instead of six separate ones

Further work in this area is expected as these types of hidden overheads become more noticeable with increasing core counts.

##### Specialised reduction

A specialised `Foam::reduce` for `MinMax` with `sumOp` has been added. This passes directly to the corresponding MPI reductions without any intermediate tree communication or serialisation/deserialisation overhead.


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/plugins -->

QUICK LINKS

[PYBFOAM](#pybfoam)
[PYOFTOOLS](#pyoftools)
[VTKHDF](#vtkhdf)

# v2606: Plugins

## Community contribution: pybFoam

 [TOP](#)

This release introduces Python bindings for OpenFOAM, called pybFoam, developed by Henning Scheufler. Many thanks for this contribution!

Python has gained increasing relevance for scientific computing, data analysis, machine learning, and as general\-purpose glue for workflows. Many of the methods becoming increasingly relevant to CFD are developed in this ecosystem, including data\-driven turbulence closures, surrogate and reduced\-order models, and physics\-informed neural networks. The pybFoam project makes these methods more accessible and can serve as an entry point into the Python ecosystem. By including these bindings, we hope to encourage their use and provide a well\-coordinated Python/OpenFOAM interface.

`pybFoam` is built on top of nanobind and exposes the OpenFOAM classes within Python. The following features are currently bound:

* **Core types** – `Time`, `fvMesh`, `dictionary`, and the `volField` and `surfaceField` families, with field data exposed directly to NumPy.
* **Field operations** – arithmetic and mathematical operations on fields, including `cos`, `sin`, and other element\-wise functions.
* **Finite\-volume operators** – `fvc` and `fvm` operators (grad, div, laplacian, ddt, and others) bound to the OpenFOAM implementation.
* **Sampling** – surface and line sampling with interpolation.
* **Models** – turbulence and thermophysical model bindings.
* **Meshing** – blockMesh, snappyHexMesh, and checkMesh.
* **Embedded solver** – an interpreter that can be embedded in a solver or library.

Below is an example of how to load the pressure field, compute its gradient, and create a NumPy view of the resulting field:

```
import pybFoam as pyb
import numpy as np

runTime = pyb.Time(".", ".")
mesh = pyb.fvMesh(runTime)
p = pyb.volScalarField.read_field(mesh, "p")

grad_p = pyb.fvc.grad(p)
np_p = np.asarray(p["internalField"])
```
Further documentation is provided on the external repository.

* **Repository** – <https://github.com/HenningScheufler/pybFoam>
* **Documentation** – <https://henningscheufler.github.io/pybFoam/index.html>

## Community contribution: pyOFTools

 [TOP](#)

pyOFTools, also developed by Henning Scheufler, builds on the infrastructure provided by pybFoam and offers a base set of Python methods for interacting with OpenFOAM.

By using Python at both ends of a run – the pre\-processing that prepares initial fields and the post\-processing that extracts results – workflows become easier to express and extend.

The library is also intended to demonstrate the following:

* how to embed the Python interpreter in OpenFOAM and use it with pybFoam
* how to extend a library with custom bindings
* how a Python library on top of pybFoam can be packaged in the Python ecosystem

pyOFTools runs its post\-processing within an OpenFOAM solver via a function object:

```
functions
{
    pyPostProcessing
    {
        libs            (embeddingPython);
        type            pyPostProcessing;
        writeControl    timeStep;
        writeInterval   1;
        pyFileName      postProcess;   // postProcess.py (no extension)
        pyClassName     postProcess;   // module-level PostProcessorBase instance
    }
}
```
This will load a user\-defined Python file `postProcess.py` and call the class `postProcess`:

```
from pyOFTools.postprocessor import PostProcessorBase
from pyOFTools.builders import field
from pyOFTools.aggregators import VolIntegrate

postProcess = PostProcessorBase()

@postProcess.Table("water_volume.csv")
def water_volume(mesh):
    return field(mesh, "alpha.water") | VolIntegrate()
```
The decorator `@postProcess.Table("water_volume.csv")` defines the output format and file name. The function body loads a field from the registry using `field(mesh, "alpha.water")` and applies operations to it. In this case, `| VolIntegrate()` integrates `alpha.water` over the domain volume.

##### Additional Features

* **surface datasets** \- `plane(mesh, point, normal)` or `iso_surface(mesh, "alpha.water", 0.5)`, then pipe into `area()` or `sample(mesh, field)` and an aggregator, e.g. `iso_surface(mesh, "alpha.water", 0.5) | area() | Sum()`.
* **point datasets** \- `line(mesh, name, start, end, n_points, field)` samples a field along a line, e.g. `line(mesh, "centreline", (0,0,0), (1,0,0), 100, "p") | Mean()`.
* **Composable pipeline** \- spatial selectors (`Box`, `Sphere`, combined with `&` / `|` / `~`), binners (`Directional`), and aggregators (`Sum`, `Mean`, `VolIntegrate`, `SurfIntegrate`) chain with the `|` operator and compose across dataset types.
* **setFields in Python** \- prepare initial `0/` fields with the *same* geometric selectors used for post\-processing, instead of `setFieldsDict`.
* **Command\-line interface** \- a `pyoftools` CLI: `pyoftools setFields <spec>` runs a `.py` or `.json` field spec against a case, plus `pyoftools version`.
* **Sampling** \- surface and line/set sampling with interpolation, reusing the same selectors and aggregators as volume data.

More details can be found in the documentation.

* **Repository** \- <https://github.com/HenningScheufler/pyOFTools>
* **Documentation** \- <https://henningscheufler.github.io/pyOFTools/index.html>

## New VTK\-HDF support

 [TOP](#)

This OpenFOAM release includes the first support for exporting OpenFOAM data to the new VTK\-HDF data format.

This native VTK data format, properly supported by ParaView 6\.1 and later, is based on HDF5 (Hierarchical Data Format). It eliminates the parsing overhead and data duplication associated with previous VTK formats, whether legacy or XML\-based. The format provides true binary file capabilities that accelerate reading and enable greater flexibility for supporting the newest VTK data models and data compositions.

One of the longer\-term benefits will be the reuse of static mesh geometries – something already possible with the Ensight formats but without requiring a separate parser. The format also opens up the possibility of adding data compression and other enhancements in future releases.

The initial bindings address the heaviest and most frequent data producers: volume geometry and fields.

Output does not yet support data compression during generation, but the HDF5 `h5repack` command can be used to apply compression afterwards.

##### The vtkhdfWrite function object

The new `vtkhdfWrite` function object is designed as a drop\-in replacement for the existing `vtkWrite` function object, supporting all of the same keywords. The `legacy` and `format` keywords are accepted but silently ignored as they are not applicable to this format.

The relevant keywords for the `vtkhdfWrite` function object are:

```
{
   type    vtkhdfWrite;
   libs    (foam-vtkhdfWrite);
   ...
}
```
If sufficient interest emerges from this initial offering, further support for different OpenFOAM data generators, time\-series data, and static geometries will be considered for a future release.

##### The foamToVTKHDF utility

As the name suggests, the `foamToVTKHDF` utility is the VTK\-HDF counterpart to the `foamToVTK` utility. Its base functionality is largely identical, but currently only handles volume geometry and fields. Finite\-area, Lagrangian, and special\-purpose diagnostic dumps are not yet supported.

No associated tutorial examples are included, as both tools should work as drop\-in replacements for their existing counterparts.


---

<!-- https://www.openfoam.com/news/main-news/openfoam-v2606/community -->

QUICK LINKS

[THANK YOU](#thank-you)

# v2606: OpenFOAM Community

## Thank you

 [TOP](#)

A big **Thank you** to the following community members who contributed to OpenFOAM.

### Contributions: Merge requests

* [Robert Perry](https://gitlab.com/skoloCFD):
	+ [MR\#823 \- BUG: Time::setControls: avoid false\-positive in startTime consistency check (closes \#3544\)](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/823)
	+ [MR\#810 \- BUG: only compute sample statistics on valid points to prevent overflow (closes \#3526\)](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/810)
	+ [MR\#808 \- BUG: invalidTetHandling option to prevent nearWallFields crashes (closes \#3523\)](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/808)
	+ [MR\#804 \- ENH: option for specifying U field for wallShearStress](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/804)
	+ [MR\#803 \- BUG: noise utility ignores ensight collateTimes writeOption](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/803)
	+ [MR\#801 \- ENH: createPatch \-fields option allows preserving fields](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/801)
	+ [MR\#800 \- ENH: add snappyHexMesh \-no\-intermediate\-write option](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/800)
	+ [MR\#798 \- ENH: option for selecting which porous cellzones to include in forces/forcesCoeffs](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/798)
	+ [MR\#797 \- ENH: yPlus field entry to allow user\-selection of U field used](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/797)
	+ [MR\#786 \- fix for fusedGauss tbb link issue](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/786)
* [tulasihazarath\-mcw](https://gitlab.com/tulasihazarath-mcw):
	+ [MR\#829 \- ENH: Enable support for windows on ARM](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/829)
* [Sajad Khodadadi](https://gitlab.com/sajad.khodadadi):
	+ [MR\#815 \- Add immersed boundary framework with library, solvers, tutorials and core integration changes](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/815)
	+ [MR\#814 \- solver\-level immersed boundary framework with library, solvers, tutorials, and required core integration changes](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/814)
* [Qizhe Wen](https://gitlab.com/wenqizhe558):
	+ [MR\#816 \- Adopt limitedCubic for non\-orthogonal meshes](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/816)
* [Thorsten Zirwes](https://gitlab.com/TZirwes):
	+ [MR\#812 \- Bugfix for the cubic scheme from https://bugs.openfoam.org/view.php?id\=4279](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/812)
* [Marine Lasbleis](https://gitlab.com/marinelasbleis):
	+ [MR\#827 \- BUG: interFoam : off\-centered coefficient not correctly used in alpha eqn](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/827)
	+ [MR\#793 \- correction to inversedistance to add .correctBoundaryConditions()](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/793)
* [David Von Rüden](https://gitlab.com/OpenFoe):
	+ [MR\#805 \- tutorials: source CleanFunctions in Allclean for sloshingTank2D in interFoam](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/805)
* [Ilya Popov](https://gitlab.com/ipopov):
	+ [MR\#790 \- Batch ln calls in wmakeLnInclude](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/790)
* [Zhisong Li](https://gitlab.com/zhisongli):
	+ [MR\#785 \- fix bugs in BoussinesqWaveModel.C, GrimshawWaveModel.C and McCowanWaveModel.C](https://gitlab.com/openfoam/core/openfoam/-/merge_requests/785)

### Contributions: Issue tracking

* [Gerasimos Chourdakis (MakisH)](https://gitlab.com/MakisH): v2512: Corrupted debian packages for Ubuntu 24\.04 [GL\#3480](https://gitlab.com/openfoam/core/openfoam/-/work_items/3480)
* [Masashi Imano (masaz)](https://gitlab.com/masaz): Broken link for ThirdParty\-v2512\.tgz (404 Not Found) [GL\#3482](https://gitlab.com/openfoam/core/openfoam/-/work_items/3482)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): pitzDaily\_fused tutorial does not run [GL\#3485](https://gitlab.com/openfoam/core/openfoam/-/work_items/3485)
* [franco otaola (otaola.franc)](https://gitlab.com/otaola.franc): Issue with projection in blockmesh [GL\#3490](https://gitlab.com/openfoam/core/openfoam/-/work_items/3490)
* [Carsten Thorenz (cthorenz)](https://gitlab.com/cthorenz): fvOptions: Geometric selection moves into opposite direction [GL\#3491](https://gitlab.com/openfoam/core/openfoam/-/work_items/3491)
* [Carsten Thorenz (cthorenz)](https://gitlab.com/cthorenz): fvOptions: Geometric selection can generate wrong console info [GL\#3492](https://gitlab.com/openfoam/core/openfoam/-/work_items/3492)
* [xpqiu (xpqiu)](https://gitlab.com/xpqiu): unexpected behavior of ensightSurfaceWriter in SPDP mode [GL\#3493](https://gitlab.com/openfoam/core/openfoam/-/work_items/3493)
* [Frederic Simonis (fsimonis)](https://gitlab.com/fsimonis): Package mismatch on Ubuntu 25\.10 questing [GL\#3496](https://gitlab.com/openfoam/core/openfoam/-/work_items/3496)
* [Asahi Yoshimitsu (YAsahi)](https://gitlab.com/YAsahi): chtMultiRegionTwoPhaseEulerFoam with jouleHeatingSource would read a nonexistent time directory [GL\#3499](https://gitlab.com/openfoam/core/openfoam/-/work_items/3499)
* [xpqiu (xpqiu)](https://gitlab.com/xpqiu): possible bug in residualControl within the PIMPLE dict [GL\#3500](https://gitlab.com/openfoam/core/openfoam/-/work_items/3500)
* [Santiago Marquez Damian (santiagomarquezd)](https://gitlab.com/santiagomarquezd): alpha2 is not updated anymore after created in twoPhaseMixture [GL\#3501](https://gitlab.com/openfoam/core/openfoam/-/work_items/3501)
* [Marine Lasbleis (marinelasbleis)](https://gitlab.com/marinelasbleis): inverseDistance diffusivity [GL\#3502](https://gitlab.com/openfoam/core/openfoam/-/work_items/3502)
* [Mahi\_848 (MahishMohan)](https://gitlab.com/MahishMohan): patchDistanceToCell/TopoSet [GL\#3503](https://gitlab.com/openfoam/core/openfoam/-/work_items/3503)
* [yongsheng fu (fuys)](https://gitlab.com/fuys): wmakeFilesAndOptions: command not found [GL\#3505](https://gitlab.com/openfoam/core/openfoam/-/work_items/3505)
* [Masaru Sato (satorccm)](https://gitlab.com/satorccm): the sign for eqn.diag() and eqn.source() for coded source term is reversed [GL\#3508](https://gitlab.com/openfoam/core/openfoam/-/work_items/3508)
* [David Von Ruden (OpenFoe)](https://gitlab.com/OpenFoe): Third\-Party\-v2512 Scotch 6\.1\.0 fails to build on Ubuntu 25\.10 [GL\#3510](https://gitlab.com/openfoam/core/openfoam/-/work_items/3510)
* [Yannick Eberhard (Yannick.Eberhard)](https://gitlab.com/Yannick.Eberhard): propellerInfo functionObject calculates wrong cylindrical velocites [GL\#3511](https://gitlab.com/openfoam/core/openfoam/-/work_items/3511)
* [Anna Hochberger (hochbean)](https://gitlab.com/hochbean): Adding solar radiation cools down surfaces [GL\#3512](https://gitlab.com/openfoam/core/openfoam/-/work_items/3512)
* [GiuseppeGq20 (GiuseppeGq20\)](https://gitlab.com/GiuseppeGq20): SnappyHexMesh error: wheelRotMesh static mesh fail with openfoam version newer than v2106 [GL\#3513](https://gitlab.com/openfoam/core/openfoam/-/work_items/3513)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): snappyHexMesh option to only write final mesh, no intermediate steps [GL\#3515](https://gitlab.com/openfoam/core/openfoam/-/work_items/3515)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): fix for redistributePar failures when changing node count with hostCollated [GL\#3516](https://gitlab.com/openfoam/core/openfoam/-/work_items/3516)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): significant fusedGauss differences on driveAer test cases [GL\#3519](https://gitlab.com/openfoam/core/openfoam/-/work_items/3519)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): Speeding up snappyHexMesh and utilities \- per\-phase decomp and foamMeshPipeline [GL\#3520](https://gitlab.com/openfoam/core/openfoam/-/work_items/3520)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): nearWallFields crashes if sampled wall face can’t be placed in a valid tet decomposition [GL\#3523](https://gitlab.com/openfoam/core/openfoam/-/work_items/3523)
* [Mark Olesen (olesenm)](https://gitlab.com/olesenm): add support for python bindings [GL\#3524](https://gitlab.com/openfoam/core/openfoam/-/work_items/3524)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): sample utility crashes when invalid points are present during single precision solve [GL\#3526](https://gitlab.com/openfoam/core/openfoam/-/work_items/3526)
* [Zhouping Li (bajfi)](https://gitlab.com/bajfi): ISpanStream Bug [GL\#3530](https://gitlab.com/openfoam/core/openfoam/-/work_items/3530)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): applyBoundaryLayer should exclude slip walls, movingWallVelocity patches, etc. [GL\#3534](https://gitlab.com/openfoam/core/openfoam/-/work_items/3534)
* [Sajad Khodadadi (sajad.khodadadi)](https://gitlab.com/sajad.khodadadi): solver\-level immersed boundary framework with library, solvers, tutorials, and required core integration changes [GL\#3536](https://gitlab.com/openfoam/core/openfoam/-/work_items/3536)
* [tulasihazarath\-mcw (tulasihazarath\-mcw)](https://gitlab.com/tulasihazarath-mcw): OpenFOAM support for Windows on ARM (ARM64\) [GL\#3538](https://gitlab.com/openfoam/core/openfoam/-/work_items/3538)
* [Robert Perry (skoloCFD)](https://gitlab.com/skoloCFD): BUG: single precision DES fails to restart: Start time is not the same for all processors [GL\#3544](https://gitlab.com/openfoam/core/openfoam/-/work_items/3544)
* [Zhouping Li (bajfi)](https://gitlab.com/bajfi): objectRegistry Bug [GL\#3550](https://gitlab.com/openfoam/core/openfoam/-/work_items/3550)
* [Alexey Matveichev (alexey.matveichev)](https://gitlab.com/alexey.matveichev): ENH: Convergence controls for multi\-region solvers [GL\#3555](https://gitlab.com/openfoam/core/openfoam/-/work_items/3555)
* [Zhouping Li (bajfi)](https://gitlab.com/bajfi): PatchInteraction for symmetry patch [GL\#3556](https://gitlab.com/openfoam/core/openfoam/-/work_items/3556)
* [Zhouping Li (bajfi)](https://gitlab.com/bajfi): Probobility compare error of the StochasticCollision [GL\#3559](https://gitlab.com/openfoam/core/openfoam/-/work_items/3559)
* [Rbemi (Rbemi)](https://gitlab.com/Rbemi): regionFaMaxCo not read anymore [GL\#3560](https://gitlab.com/openfoam/core/openfoam/-/work_items/3560)
