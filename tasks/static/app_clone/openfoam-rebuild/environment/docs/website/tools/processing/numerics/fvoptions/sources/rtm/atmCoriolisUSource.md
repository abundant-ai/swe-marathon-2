<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmCoriolisUSource -->

# atmCoriolisUSource

## Properties

* The `atmCoriolisUSource` applies corrections to incorporate
the horizontal and vertical components of the Coriolis force
for which the rotating frame is Earth.
* The Coriolis force is an inertial or fictitious force that acts on
objects that are in motion within a frame of reference that rotates with
respect to an inertial frame.
* In the atmospheric boundary layer context, for the "Coriolis effect",
the rotating reference frame implied is almost always Earth.
Because Earth spins, Earth\-bound observers need to account for the
Coriolis force to correctly analyze the motion of objects. Earth
completes one rotation per day, so for motions of everyday objects the
Coriolis force is usually quite small compared with other forces; its
effects generally become noticeable only for motions occurring over large
distances and long periods of time, such as large\-scale movement of air in
the atmosphere or water in the ocean. Such motions are constrained by the
surface of Earth, so only the horizontal component of the Coriolis
force is generally important.
* The `atmCoriolisUSource` can be applied on any RAS turbulence model.
* The `atmCoriolisUSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied on:

`U`
: Velocity \[m/s]

Required fields:

`U`
: Velocity \[m/s]

## Model equations

The model expression:

fM−\=αρ((2Ω)×u) f\_M \-\= \\alpha \\rho ((2 \\Omega) \\times \\u )fM​−\=αρ((2Ω)×u)
Where:

fMf\_MfM​
: fvMatrix of the velocity field

Ω\\OmegaΩ
: Rotation vector of the rotating reference frame relative to the inertial frame \[rad/s]

u\\uu
: Velocity field \[m/s]

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmCoriolisUSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmCoriolisUSource;

    atmCoriolisUSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Conditional mandatory entries (unmodifiable)
        // Select either of the below

        // Option-1: to directly input rotation vector
        Omega        (0 0 5.65156e-5);

        // Option-2: to indirectly input rotation vector
        // by a latitude-period pair
        latitude                   51.971;
        planetaryRotationPeriod    23.9344694;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmCoriolisUSource | word | yes | \- |
| latitude | Geographic coordinate specifying the north–south position of a point on the surface of a planetary body \[deg] | scalar | conditional | 0\.0 |
| planetaryRotationPeriod | Rotation period of the planetary body \[h] | scalar | conditional | 23\.9344694 |
| Omega | Rotation vector of the rotating reference frame relative to the inertial frame \[rad/s] | vector | conditional | (0 0 0\) |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmCoriolisUSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmCoriolisUSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
