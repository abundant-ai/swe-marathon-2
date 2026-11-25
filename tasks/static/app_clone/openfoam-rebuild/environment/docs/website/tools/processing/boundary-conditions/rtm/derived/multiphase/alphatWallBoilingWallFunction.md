<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/alphatWallBoilingWallFunction -->

# alphatWallBoilingWallFunction

## Description

The `compressible::alphatWallBoilingWallFunction` is a boundary condition that provides
A thermal wall function for simulation of boiling wall.

This alpha wall function can handle the following regimes:

* single phase
* sub\-cooled nucleate wall boiling
* transitional boiling
* film boiling

The wall function uses a partition method to transfer heat either
to the liquid or vapor phase. At the moment, this function works
in a wall temperature fixed mode, i.e. there is no consideration
for the sudden change of heat transfer coefficient (htc) after
reaching TDBN (deviation from nucleate boiling temperature).

For the single phase non\-boiling regime the standard
`JayatillekeWallFunction` is used.

For the sub\-cool nucleate boiling regime the following runtime
selectable submodels are used:

* nucleation site density
* bubble departure frequency
* bubble departure diameter

Implements a version of the well\-known RPI wall boiling model
(Kurul \& Podowski, 1991\). The model implementation is similar to the model
described by Peltola \& Pättikangas (2012\) but has been extended with the
wall heat flux partitioning models.

Alternatively a correlation can be used instead of the RPI wall boiling model.
If the keyword nucleatingModel a model is provided the BC uses it
instead of the RPI model.

The transition boiling regime flux (TBF) is modelled following
a temperature based linear interpolation between the critical heat flux
(CHF) and the minimum heat flux (MHF) in such a way that when the wall
temperature is between the range of TDBN and the Leidenfrost temperature
(TLeiden) a linear interpolation is used between CHF and MHF.

Thus, the following models are required:

* LeidenfrostModel
* CHFModel
* CHFSubCoolModel
* MHFModel
* TDNBModel
* filmBoilingModel

The linear interpolation is as follows:

TBF\=CHF∗ϕ\+(1−ϕ)∗MHF TBF \= CHF\*\\phi \+ (1 \- \\phi)\*MHFTBF\=CHF∗ϕ\+(1−ϕ)∗MHF
with:

ϕ\=wp∗(Tw−TDNB)/(TLeiden−TDNB) \\phi \= w\_p\*(T\_w \- T\_{DNB})/(T\_{Leiden} \- T\_{DNB})ϕ\=wp​∗(Tw​−TDNB​)/(TLeiden​−TDNB​)
where:

| Property | Description |
| --- | --- |
| wpw\_pwp​ | Model constant |
| TwT\_wTw​ | Wall temperature \[K] |

#### References

```
Srinivasan, V., Moon, K. M., Greif, D.,
Wang, D. M., & Kim, M. H. (2010).
Numerical simulation of immersion quenching
process of an engine cylinder head.
Applied Mathematical Modelling, 34(8), 2111-2128.
DOI:10.1016/j.apm.2009.10.023

Kurul, N., & Podowski, M. Z. (1991).
On the modeling of multidimensional effects in boiling channels.
Proceedings of the 27th National Heat Transfer Conference.
Minneapolis, Minn, USA, July 28-31, 1991.
ISBN: 0-89448-162-1, pp. 30-40

Peltola, J., & Pättikangas, T. (2012).
Development and validation of a boiling model
for OpenFOAM multiphase solver.
Proceedings of the CFD4NRS-4. p. 59.
Daejeon, Democratic People's Republic of Korea, September 10-12, 2012.

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
    type            compressible::alphatWallBoilingWallFunction;
    phaseType       <word>;
    otherPhase      <word>;
    relax           <Function1<scalar>>;

    partitioningModel
    {
        type        Lavieville;
        alphaCrit   0.2;
    }

    // Conditional entries

        // Option-1: phaseType=vapor

            // Optional entries
            LeidenfrostModel
            {
                type        Spiegler;
                Tcrit       647;
            }

            filmBoilingModel
            {
                type        Bromley;
            }

        // Option-2: phaseType=liquid
        nucleationSiteModel
        {
            type        LemmertChawla;
        }

        departureDiamModel
        {
            type        TolubinskiKostanchuk;
        }

        departureFreqModel
        {
            type        Cole;
        }

            // Optional entries
            LeidenfrostModel
            {
                type        Spiegler;
                Tcrit       647;
            }

            CHFModel
            {
                type        Zuber;
            }

            CHFSubCoolModel
            {
                type        HuaXu;
                Kburn       0.5;
            }

            MHFModel
            {
                type        Jeschar;
                Kmhf        1;
            }

            TDNBModel
            {
                type        Schroeder;
            }

            filmBoilingModel
            {
                type        Bromley;
            }

            dDep    <scalarField>;
            K       <scalar>;
            wp      <scalar>;
            qQuenching <scalarField>;

    // Optional entries
    alphatConv      <scalarField>;

    //Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::alphatWallBoilingWallFunction` | word | yes | \- |
| `phaseType` | Name of phase type | word | yes | \- |
| `otherPhase` | Name of other phase | word | yes | \- |
| `relax` | Relaxation factor for dmdt | Function1\<scalar\> | yes | \- |
| `alphatConv` | Convective turbulent thermal diffusivity | scalarField | no | 0 |
| `partitioningModel` | Run\-time selected heat flux partitioning model | dict | yes | \- |

Options for the `phaseType` and `otherPhase` entries:

| Property | Description |
| --- | --- |
| `vapor` | Vapor phase |
| `liquid` | Liquid phase |

when `phaseType=liquid`:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `nucleationSiteModel` | Nucleation site density model | dict | yes | \- |
| `departureDiamModel` | Bubble departure diameter model | dict | yes | \- |
| `departureFreqModel` | Bubble departure frequency model | dict | yes | \- |
| `LeidenfrostModel` | Leidenfrost temperature model | dict | no | \- |
| `CHFModel` | Critical heat flux model | dict | no | \- |
| `CHFSubCoolModel` | CHF sub\-cool model | dict | no | \- |
| `MHFModel` | Minium heat flux model | dict | no | \- |
| `TDNBModel` | Departure from nulceate boiling model | dict | no | \- |
| `filmBoilingModel` | Film boiling model | dict | no | \- |
| `K` | Model constant for area of bubbles | scalar | no | 4\.0 |
| `wp` | Wetting parameter for transient boiling | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* alphatPhaseChangeJayatillekeWallFunctionFvPatchScalarField.H

## Further information

Tutorial:

* [wallBoiling1D\_2phase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingMultiphaseEulerFoam/RAS/wallBoiling1D_2phase)

Source code:

* [alphatWallBoilingWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/alphatWallBoilingWallFunction)

API:

* [Foam::compressible::alphatWallBoilingWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_alphatWallBoilingWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
