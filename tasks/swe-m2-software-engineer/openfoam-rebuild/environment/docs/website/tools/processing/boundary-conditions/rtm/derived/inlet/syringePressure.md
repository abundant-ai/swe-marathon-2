<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/syringePressure -->

# syringePressure

## Description

The `syringePressure` is a boundary condition
that provides a pressure condition, obtained from a
zero\-D model of the cylinder of a syringe.

The syringe cylinder is defined by its initial volume, piston area and
velocity profile specified by regions of constant acceleration, speed
and deceleration. The gas in the cylinder is described by its initial
pressure and compressibility which is assumed constant, i.e. isothermal
expansion/compression.

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
    type            syringePressure;
    Ap              <scalar>;
    Sp              <scalar>;
    VsI             <scalar>;
    tas             <scalar>;
    tae             <scalar>;
    tds             <scalar>;
    tde             <scalar>;
    psI             <scalar>;
    psi             <scalar>;
    ams             <scalar>;

    // Optional entries
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `syringePressure` | word | yes | \- |
| `Ap` | Syringe piston area \[m^2] | scalar | yes | \- |
| `Sp` | Syringe piston speed \[m/s] | scalar | yes | \- |
| `VsI` | Initial syringe volume \[m^3] | scalar | yes | \- |
| `tas` | Start of piston acceleration \[s] | scalar | yes | \- |
| `tae` | End of piston acceleration \[s] | scalar | yes | \- |
| `tds` | Start of piston deceleration \[s] | scalar | yes | \- |
| `tde` | End of piston deceleration \[s] | scalar | yes | \- |
| `psI` | Initial syringe pressure \[Pa] | scalar | yes | \- |
| `psi` | Gas compressibility \[m^2/s^2] | scalar | yes | \- |
| `ams` | Added (or removed) gas mass \[kg] | scalar | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [syringePressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/syringePressure)

API:

* [Foam::syringePressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_syringePressureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
