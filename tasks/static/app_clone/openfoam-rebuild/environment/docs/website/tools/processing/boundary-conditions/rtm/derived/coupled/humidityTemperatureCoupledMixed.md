<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/humidityTemperatureCoupledMixed -->

# humidityTemperatureCoupledMixed

## Description

The `humidityTemperatureCoupledMixed` is a mixed coupled boundary condition for
temperature to be used at the coupling interface between fluid and solid regions.

Various governing equations of this boundary condition are based on
Bergman et al.[1](../../../../../../references.md#Bergman_2011).

The condition assumes a drop\-wise type of condensation, whereby its heat
transfer Nusselt number is calculated using:

Nu\=51104\+2044(T−273\.15) if  T\>295  \&  T\<373 Nu \= 51104 \+ 2044 (T \- 273\.15\) \\, \\text{if} \\, \\, T \> 295 \\, \\, \\\& \\, \\, T \< 373Nu\=51104\+2044(T−273\.15)ifT\>295\&T\<373
Nu\=255510  if  T\>373 Nu \= 255510 \\, \\, \\text{if} \\, \\, T \> 373Nu\=255510ifT\>373
The mass transfer correlation used is:

hm\=DabShL h\_m
 \=
 D\_{ab} \\frac{Sh}{L}hm​\=Dab​LSh​
The Sherwood number is calculated using:

Sh\=0\.664Re12Sc13  if  Re\<5\.0E\+05 Sh \= 0\.664 Re^\\frac{1}{2} Sc^\\frac{1}{3} \\, \\, \\text{if} \\, \\, Re \< 5\.0E\+05Sh\=0\.664Re21​Sc31​ifRe\<5\.0E\+05
Sh\=0\.037Re45Sc13  if  Re\>5\.0E\+05 Sh \= 0\.037 Re^\\frac{4}{5} Sc^\\frac{1}{3} \\, \\, \\text{if} \\, \\, Re \> 5\.0E\+05Sh\=0\.037Re54​Sc31​ifRe\>5\.0E\+05
where:

| Property | Description |
| --- | --- |
| DabD\_{ab}Dab​ | Mass vapour difussivity |
| LLL | Characteristic length |
| ShShSh | Sherwood number |
| ReReRe | Reynolds number |
| ScScSc | Schmidt number |
| NuNuNu | Nusselt number |

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

On the fluid side:

```
<patchName>
{
    // Mandatory entries
    type            humidityTemperatureCoupledMixed;
    mode            <word>;

    // Optional entries
    p               <word>;
    U               <word>;
    rho             <word>;
    mu              <word>;
    Tnbr            <word>;
    qrNbr           <word>;
    qr              <word>;
    specie          <word>;
    thicknessLayers <scalarList>;

    // Conditional entries

        // when 'thicknessLayers' entry is present
        kappaLayers         <scalarList>;

        // when 'mode' == 'constantMass'
        thickness           <scalarField>;
        cp                  <scalarField>;
        rho                 <scalarField>;

        // when 'mode' != 'constantMass'
        carrierMolWeight    <scalar>;
        L                   <scalar>;
        Tvap                <scalar>;
        liquid              <dict>;
        thickness           <scalarField>;

    // Inherited entries
    ...
}

```

On the solid side:

```
<patchName>
{
    // Mandatory entries
    type            humidityTemperatureCoupledMixed;

    // Optional entries
    p               <word>;
    U               <word>;
    rho             <word>;
    mu              <word>;
    Tnbr            <word>;
    qrNbr           <word>;
    qr              <word>;
    specie          <word>;
    thicknessLayers <scalarList>;

    // Conditional entries

        // when 'thicknessLayers' entry is present
        kappaLayers         <scalarList>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `humidityTemperatureCoupledMixed` | word | yes | \- |
| `mode` | Operation mode | word | yes | \- |
| `p` | Name of pressure field | word | no | `p` |
| `U` | Name of velocity field | word | no | `U` |
| `rho` | Name of density field | word | no | `rho` |
| `mu` | Name of dynamic viscosity field | word | no | `thermo:mu` |
| `Tnbr` | Name of neighbour temperature field | word | no | `T` |
| `qrNbr` | Name of neighbour radiative heat flux field | word | no | `none` |
| `qr` | Name of radiative heat flux field | word | no | `none` |
| `specie` | Name of specie field | word | no | `none` |
| `thicknessLayers` | List of kappa\-layer thicknesses | scalarList | no | \- |
| `kappaLayers` | List of kappas corresponding to thicknesses | scalarList | conditional | \- |
| `thickness` | Thickness field | scalarField | conditional | \- |
| `cp` | Specific heat capacity field | scalarField | conditional | \- |
| `rho` | Density field | scalarField | conditional | \- |
| `carrierMolWeight` | Carrier molecular weight | scalar | conditional | \- |
| `L` | Characteristic length of the wall | scalar | conditional | \- |
| `Tvap` | Vaporisation temperature | scalar | conditional | \- |
| `liquid` | Liquid properties | dict | conditional | \- |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)
* [Foam::temperatureCoupledBase](https://api.openfoam.com/2606/Foam_temperatureCoupledBase.html)
* [Foam::liquidProperties](https://api.openfoam.com/2606/Foam_liquidProperties.html)

Options for the `mode` entry:

| Property | Description |
| --- | --- |
| `constantMass` | Thermal inertia only |
| `condensation` | Condensation only |
| `evaporation` | Evaporation only |
| `condensationAndEvaporation` | Simultaneous condensation and evaporation |

* The correlation used to calculate `Tdew` is for water vapour.
* A scalar transport equation for the carrier specie is required, e.g.
supplied via a function object or in the main solver. This specie
transports the vapour phase in the main ragion.
* The boundary condition of this specie on the coupled wall must be
`fixedGradient` in order to allow condensation or evaporation of the
vapour in or out of this wall.
* There is no mass flow on the wall, i.e. the mass condensed on a face
remains on that face. It uses a 'lumped mass' model to include thermal
inertia effects.
* With `mode==condensation`, when the wall temperature (Tw) is below the dew
temperature (Tdew) condesation takes place and the resulting condensed mass
is stored on the wall.
* With `mode==evaporation`, initial mass is vaporized when the wall temperature
(Tw) is above the input vaporization temperature (Tvap).

## Further information

Tutorial:

* [windshieldCondensation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam/windshieldCondensation)

Source code:

* [humidityTemperatureCoupledMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/humidityTemperatureCoupledMixed)

API:

* [Foam::compressible::humidityTemperatureCoupledMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_humidityTemperatureCoupledMixedFvPatchScalarField.html)

**History:** Introduced in version [v1706](https://www.openfoam.com/news/main-news/openfoam-v1706)
